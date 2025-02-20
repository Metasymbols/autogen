# 颈圈：I：E7
import datetime
import io
import os
import re
import time
from typing import List, Optional, Tuple, Union

# TODO：修复未关注的导入
from markitdown import (FileConversionException, MarkItDown,  # 类型：忽略
                        UnsupportedFormatException)


class MarkdownFileBrowser:
    """
    (In preview) An extremely simple Markdown-powered file browser.
    """

    # TODO：修复未关注的导入
    def __init__(  # 类型：忽略
        self, viewport_size: Union[int, None] = 1024 * 8
    ):
        """
        Instantiate a new MarkdownFileBrowser.

        Arguments:
            viewport_size: Approximately how many *characters* fit in the viewport. Viewport dimensions are adjusted dynamically to avoid cutting off words (default: 8192).
        """
        self.viewport_size = viewport_size  # 仅适用于标准 uri 类型
        self.history: List[Tuple[str, float]] = list()
        self.page_title: Optional[str] = None
        self.viewport_current_page = 0
        self.viewport_pages: List[Tuple[int, int]] = list()
        self._markdown_converter = MarkItDown()
        self.set_path(os.getcwd())
        self._page_content: str = ""
        self._find_on_page_query: Union[str, None] = None
        self._find_on_page_last_result: Union[int, None] = None  # 最后结果的位置

    @property
    def path(self) -> str:
        """Return the path of the current page."""
        if len(self.history) == 0:
            return os.getcwd()
        else:
            return self.history[-1][0]

    def set_path(self, path: str) -> None:
        """Sets the path of the current page.
        This will result in the file being opened for reading.

        Arguments:
            path: An absolute or relative path of the file or directory to open."
        """

        # 处理相对路径
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            if os.path.isfile(self.path):
                path = os.path.abspath(os.path.join(
                    os.path.dirname(self.path), path))
            elif os.path.isdir(self.path):
                path = os.path.abspath(os.path.join(self.path, path))
            # 如果既不是文件也不是目录，则逐字记录

        self.history.append((path, time.time()))
        self._open_path(path)
        self.viewport_current_page = 0
        self.find_on_page_query = None
        self.find_on_page_viewport = None

    @property
    def viewport(self) -> str:
        """Return the content of the current viewport."""
        bounds = self.viewport_pages[self.viewport_current_page]
        return self.page_content[bounds[0]: bounds[1]]

    @property
    def page_content(self) -> str:
        """Return the full contents of the current page."""
        return self._page_content

    def _set_page_content(self, content: str, split_pages: bool = True) -> None:
        """Sets the text content of the current page."""
        self._page_content = content

        if split_pages:
            self._split_pages()
        else:
            self.viewport_pages = [(0, len(self._page_content))]

        if self.viewport_current_page >= len(self.viewport_pages):
            self.viewport_current_page = len(self.viewport_pages) - 1

    def page_down(self) -> None:
        """Move the viewport down one page, if possible."""
        self.viewport_current_page = min(
            self.viewport_current_page + 1, len(self.viewport_pages) - 1)

    def page_up(self) -> None:
        """Move the viewport up one page, if possible."""
        self.viewport_current_page = max(self.viewport_current_page - 1, 0)

    def find_on_page(self, query: str) -> Union[str, None]:
        """Searches for the query from the current viewport forward, looping back to the start if necessary."""

        # 我们是通过之前使用相同查询的 find_on_page 搜索到达这里的吗？
        # 如果是，则映射到find_next
        if query == self._find_on_page_query and self.viewport_current_page == self._find_on_page_last_result:
            return self.find_next()

        # 好的，这是从当前视口开始的新搜索
        self._find_on_page_query = query
        viewport_match = self._find_next_viewport(
            query, self.viewport_current_page)
        if viewport_match is None:
            self._find_on_page_last_result = None
            return None
        else:
            self.viewport_current_page = viewport_match
            self._find_on_page_last_result = viewport_match
            return self.viewport

    def find_next(self) -> Union[str, None]:
        """Scroll to the next viewport that matches the query"""

        if self._find_on_page_query is None:
            return None

        starting_viewport = self._find_on_page_last_result
        if starting_viewport is None:
            starting_viewport = 0
        else:
            starting_viewport += 1
            if starting_viewport >= len(self.viewport_pages):
                starting_viewport = 0

        viewport_match = self._find_next_viewport(
            self._find_on_page_query, starting_viewport)
        if viewport_match is None:
            self._find_on_page_last_result = None
            return None
        else:
            self.viewport_current_page = viewport_match
            self._find_on_page_last_result = viewport_match
            return self.viewport

    def _find_next_viewport(self, query: Optional[str], starting_viewport: int) -> Union[int, None]:
        """Search for matches between the starting viewport looping when reaching the end."""

        if query is None:
            return None

        # 规范化查询，并转换为正则表达式
        nquery = re.sub(r"\*", "__STAR__", query)
        nquery = " " + (" ".join(re.split(r"\W+", nquery))).strip() + " "
        nquery = nquery.replace(" __STAR__ ", "__STAR__ ")  # 将孤立的星星与先前的单词合并
        nquery = nquery.replace("__STAR__", ".*").lower()

        if nquery.strip() == "":
            return None

        idxs: List[int] = list()
        idxs.extend(range(starting_viewport, len(self.viewport_pages)))
        idxs.extend(range(0, starting_viewport))

        for i in idxs:
            bounds = self.viewport_pages[i]
            content = self.page_content[bounds[0]: bounds[1]]

            # TODO：删除 Markdown 链接和图像
            ncontent = " " + \
                (" ".join(re.split(r"\W+", content))).strip().lower() + " "
            if re.search(nquery, ncontent):
                return i

        return None

    def open_path(self, path: str) -> str:
        """Open a file or directory in the file surfer."""
        self.set_path(path)
        return self.viewport

    def _split_pages(self) -> None:
        """Split the page contents into pages that are approximately the viewport size. Small deviations are permitted to ensure words are not broken."""
        # 处理空页
        if len(self._page_content) == 0:
            self.viewport_pages = [(0, 0)]
            return

        # 将视口分成页面
        self.viewport_pages = []
        start_idx = 0
        while start_idx < len(self._page_content):
            end_idx = min(start_idx + self.viewport_size,
                          len(self._page_content))  # 类型：忽略[运算符]
            # 调整到以空格结束
            while end_idx < len(self._page_content) and self._page_content[end_idx - 1] not in [" ", "\t", "\r", "\n"]:
                end_idx += 1
            self.viewport_pages.append((start_idx, end_idx))
            start_idx = end_idx

    def _open_path(
        self,
        path: str,
    ) -> None:
        """打开文件进行阅读，并在此过程中将其转换为 Markdown。

        论据：
            path：要打开的文件或目录的路径。
        """
        try:
            if os.path.isdir(path):  # TODO：修复 markdown_converter 类型
                res = self._markdown_converter.convert_stream(  # 类型：忽略
                    io.StringIO(self._fetch_local_dir(path)), file_extension=".txt"
                )
                self.page_title = res.title
                self._set_page_content(res.text_content, split_pages=False)
            else:
                res = self._markdown_converter.convert_local(path)
                self.page_title = res.title
                self._set_page_content(res.text_content)
        except UnsupportedFormatException:
            self.page_title = "UnsupportedFormatException"
            self._set_page_content(f"# 无法预览'{path}' 作为 Markdown.")
        except FileConversionException:
            self.page_title = "FileConversionException."
            self._set_page_content(f"# 转换时出错'{path}' 到 Markdown。")
        except FileNotFoundError:
            self.page_title = "FileNotFoundError"
            self._set_page_content(f"# 未找到文件： {path}")

    def _fetch_local_dir(self, local_path: str) -> str:
        """R生成 HTML 中的本地目录列表，以帮助通过“file://”协议浏览本地文件。
        通过以 HTML 形式呈现，管道的后续部分会将列表转换为 Markdown。

        论据：
            local_path：要列出其内容的本地目录的路径。

        返回：
            以 HTML 呈现的目录列表。
        """
        listing = f"""
# 索引{local_path}

| Name | Size | Date Modified |
| ---- | ---- | ------------- |
| .. (parent directory) | | |
"""
        for entry in os.listdir(local_path):
            size = ""
            full_path = os.path.join(local_path, entry)
            mtime = datetime.datetime.fromtimestamp(
                os.path.getmtime(full_path)).strftime("%Y-%m-%d %H:%M")

            if os.path.isdir(full_path):
                entry = entry + os.path.sep
            else:
                size = str(os.path.getsize(full_path))

            listing += f"| {entry} | {size} | {mtime} |\n"
        return listing
