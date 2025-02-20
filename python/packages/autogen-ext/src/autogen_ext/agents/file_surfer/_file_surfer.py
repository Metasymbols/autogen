import json
import traceback
from typing import List, Sequence, Tuple

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    ChatMessage,
    MultiModalMessage,
    TextMessage,
)
from autogen_agentchat.utils import remove_images
from autogen_core import CancellationToken, FunctionCall
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    LLMMessage,
    SystemMessage,
    UserMessage,
)

from ._markdown_file_browser import MarkdownFileBrowser

# 从打字扩展导入注释
from ._tool_definitions import (
    TOOL_FIND_NEXT,
    TOOL_FIND_ON_PAGE_CTRL_F,
    TOOL_OPEN_PATH,
    TOOL_PAGE_DOWN,
    TOOL_PAGE_UP,
)


class FileSurfer(BaseChatAgent):
    """MagenticOne 使用的代理，充当本地文件预览器。 FileSurfer 可以打开和读取各种常见文件类型，并且可以导航本地文件层次结构。

    安装：

    .. 代码块:: bash

        pip install "autogen-ext[file-surfer]"

    参数：
        name (str): 代理人的姓名
        model_client (ChatCompletionClient)：要使用的模型（必须启用工具使用）
        description (str)：团队使用的代理描述。默认为 DEFAULT_DESCRIPTION

    """

    DEFAULT_DESCRIPTION = "可以处理本地文件的代理。"

    DEFAULT_SYSTEM_MESSAGES = [
        SystemMessage(
            content="""
        你是一个有用的人工智能助手。
        当给出用户查询时，使用可用的函数来帮助用户满足他们的请求。"""
        ),
    ]

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        description: str = DEFAULT_DESCRIPTION,
    ) -> None:
        super().__init__(name, description)
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = []
        self._browser = MarkdownFileBrowser(viewport_size=1024 * 5)

    @property
    def produced_message_types(self) -> Sequence[type[ChatMessage]]:
        return (TextMessage,)

    async def on_messages(self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken) -> Response:
        for chat_message in messages:
            if isinstance(chat_message, TextMessage | MultiModalMessage):
                self._chat_history.append(UserMessage(
                    content=chat_message.content, source=chat_message.source))
            else:
                raise ValueError(
                    f"FileSurfer 中出现意外消息： {chat_message}")

        try:
            _, content = await self._generate_reply(cancellation_token=cancellation_token)
            self._chat_history.append(AssistantMessage(
                content=content, source=self.name))
            return Response(chat_message=TextMessage(content=content, source=self.name))

        except BaseException:
            content = f"文件浏览错误：\n\n{traceback.format_exc()}"
            self._chat_history.append(AssistantMessage(
                content=content, source=self.name))
            return Response(chat_message=TextMessage(content=content, source=self.name))

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        self._chat_history.clear()

    def _get_browser_state(self) -> Tuple[str, str]:
        """
        获取浏览器的当前状态，包括标题和内容。
        """
        header = f"Path: {self._browser.path}\n"

        if self._browser.page_title is not None:
            header += f"Title: {self._browser.page_title}\n"

        current_page = self._browser.viewport_current_page
        total_pages = len(self._browser.viewport_pages)
        header += f"视口位置：显示页面 {
            current_page+1} of {total_pages}.\n"

        return (header, self._browser.viewport)

    async def _generate_reply(self, cancellation_token: CancellationToken) -> Tuple[bool, str]:
        history = self._chat_history[0:-1]
        last_message = self._chat_history[-1]
        assert isinstance(last_message, UserMessage)

        task_content = last_message.content  # 发件人的最后一条消息是一个任务

        assert self._browser is not None

        context_message = UserMessage(
            source="user",
            content=f"您的文件查看器当前已打开该文件或目录'{
                self._browser.page_title}' 有路径'{self._browser.path}'.",
        )

        task_message = UserMessage(
            source="user",
            content=task_content,
        )

        create_result = await self._model_client.create(
            messages=self._get_compatible_context(history + [context_message, task_message]),
            tools=[
                TOOL_OPEN_PATH,
                TOOL_PAGE_DOWN,
                TOOL_PAGE_UP,
                TOOL_FIND_NEXT,
                TOOL_FIND_ON_PAGE_CTRL_F,
            ],
            cancellation_token=cancellation_token,
        )

        response = create_result.content

        if isinstance(response, str):
            # 直接回答。
            return False, response

        elif isinstance(response, list) and all(isinstance(item, FunctionCall) for item in response):
            function_calls = response
            for function_call in function_calls:
                tool_name = function_call.name

                try:
                    arguments = json.loads(function_call.arguments)
                except json.JSONDecodeError as e:
                    error_str = f"文件浏览器在解码 JSON 参数时遇到错误: {
                        e}"
                    return False, error_str

                if tool_name == "open_path":
                    path = arguments["path"]
                    self._browser.open_path(path)
                elif tool_name == "page_up":
                    self._browser.page_up()
                elif tool_name == "page_down":
                    self._browser.page_down()
                elif tool_name == "find_on_page_ctrl_f":
                    search_string = arguments["search_string"]
                    self._browser.find_on_page(search_string)
                elif tool_name == "find_next":
                    self._browser.find_next()
            header, content = self._get_browser_state()
            final_response = header.strip() + "\n=======================\n" + content
            return False, final_response

        final_response = "TERMINATE"
        return False, final_response

    def _get_compatible_context(self, messages: List[LLMMessage]) -> List[LLMMessage]:
        """Ensure that the messages are compatible with the underlying client, by removing images if needed."""
        if self._model_client.model_info["vision"]:
            return messages
        else:
            return remove_images(messages)
