"""搜索结果数据模型。"""
from pydantic import BaseModel, computed_field, Field


class Paper(BaseModel):
    """统一的论文元数据，来自各搜索源的归一化结果。"""
    source: str                              # arxiv / semantic
    id: str                                  # 源内唯一 id
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str = ""
    venue: str = ""
    pdf_url: str | None = None               # 开放获取的 PDF 直链
    arxiv_id: str | None = None              # 命中 arXiv 时记录，可直接构造 PDF 链接

    @computed_field  # type: ignore[prop-decorator]
    @property
    def download_url(self) -> str | None:
        if self.arxiv_id:
            return f"https://arxiv.org/pdf/{self.arxiv_id}"
        return self.pdf_url
