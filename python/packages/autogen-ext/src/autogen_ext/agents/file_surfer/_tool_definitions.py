from autogen_core.tools import ParametersSchema, ToolSchema

TOOL_OPEN_PATH = ToolSchema(
    name="open_path",
    description="在基于文本的文件浏览器中打开某个路径中的本地文件或目录并返回当前视口内容。",
    parameters=ParametersSchema(
        type="object",
        properties={
            "path": {
                "type": "string",
                "description": "要访问的本地文件的相对或绝对路径。",
            },
        },
        required=["path"],
    ),
)


TOOL_PAGE_UP = ToolSchema(
    name="page_up",
    description="在当前文件中将视口向上滚动一页长度并返回新的视口内容。",
)


TOOL_PAGE_DOWN = ToolSchema(
    name="page_down",
    description="在当前文件中将视口向下滚动一页长度并返回新的视口内容。",
)


TOOL_FIND_ON_PAGE_CTRL_F = ToolSchema(
    name="find_on_page_ctrl_f",
    description="将视口滚动到搜索字符串第一次出现的位置。这相当于 Ctrl+F。",
    parameters=ParametersSchema(
        type="object",
        properties={
            "search_string": {
                "type": "string",
                "description": "要在页面上搜索的字符串。此搜索字符串支持“*”等通配符",
            },
        },
        required=["search_string"],
    ),
)


TOOL_FIND_NEXT = ToolSchema(
    name="find_next",
    description="将视口滚动到搜索字符串的下一个匹配项。",
)
