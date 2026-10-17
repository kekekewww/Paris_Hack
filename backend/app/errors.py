class ApiError(Exception):
    """可公開的結構化錯誤；不包含文件內容或供應商堆疊。"""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
