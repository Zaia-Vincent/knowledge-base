"""SQLAlchemy ORM model for resource chunks with pgvector embeddings."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from pgvector.sqlalchemy import Vector

from app.infrastructure.database.base import Base


class ResourceChunkModel(Base):
    """A text chunk from a processed resource, with a vector embedding.

    Chunks are created during the resource processing pipeline.
    Each resource can have multiple chunks from its extracted text and summary.
    The embedding column stores the vector for pgvector similarity search.
    """

    __tablename__ = "resource_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        String(36),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(String(30), nullable=False)  # "text", "summary"
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=True)  # 768 dims (HNSW max: 2000)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("resource_id", "chunk_type", "chunk_index", name="uq_chunk_identity"),
        Index("idx_chunks_embedding_hnsw", embedding, postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
