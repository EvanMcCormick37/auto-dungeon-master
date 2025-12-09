"""
LanceDB Vector Store for semantic search over rules, lore, and DM styles.

Provides embedding-based retrieval for RAG context assembly.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import lancedb
import pyarrow as pa
from pydantic import BaseModel


class VectorCollection(str, Enum):
    """Available vector collections."""
    RULES = "rules"           # D&D rules chunks
    LORE = "lore"             # World lore and backstory
    ACTIONS = "actions"       # Action descriptions for similarity matching
    ITEMS = "items"           # Item descriptions
    ENTITIES = "entities"     # Entity descriptions
    SPELLS = "spells"         # Spell descriptions


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

# PyArrow schemas for each collection
RULES_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("category", pa.string()),  # combat, spells, skills, conditions, abilities
    pa.field("subcategory", pa.string()),
    pa.field("source", pa.string()),    # SRD, PHB, custom
    pa.field("keywords", pa.string()),  # JSON array of keywords
    pa.field("vector", pa.list_(pa.float32(), 384)),  # all-MiniLM-L6-v2 dimension
])

LORE_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("lore_type", pa.string()),
    pa.field("related_entity_ids", pa.string()),    # JSON array of entity IDs
    pa.field("keywords", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)),
])

ACTIONS_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("name", pa.string()),
    pa.field("text", pa.string()),                  # Full action description
    pa.field("target_type", pa.string()),           # melee, ranged, effect, aoe, self
    pa.field("base_attribute", pa.string()),
    pa.field("keywords", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)),
])

ITEMS_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("name", pa.string()),
    pa.field("text", pa.string()),       # Name + description
    pa.field("item_type", pa.string()),  # weapon, armor, consumable, macguffin, misc
    pa.field("keywords", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)),
])

ENTITIES_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),       # Name + description
    pa.field("entity_type", pa.string()),  # monster, npc, creature
    pa.field("creature_type", pa.string()),  # humanoid, beast, undead, etc.
    pa.field("keywords", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)),
])

SPELLS_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),       # Name + description
    pa.field("level", pa.int32()),
    pa.field("school", pa.string()),
    pa.field("action_type", pa.string()),
    pa.field("keywords", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 384)),
])

# Map collection names to schemas
COLLECTION_SCHEMAS = {
    VectorCollection.RULES: RULES_SCHEMA,
    VectorCollection.LORE: LORE_SCHEMA,
    VectorCollection.ACTIONS: ACTIONS_SCHEMA,
    VectorCollection.ITEMS: ITEMS_SCHEMA,
    VectorCollection.ENTITIES: ENTITIES_SCHEMA,
    VectorCollection.SPELLS: SPELLS_SCHEMA,
}


# =============================================================================
# PYDANTIC MODELS FOR TYPE SAFETY
# =============================================================================

class RulesDocument(BaseModel):
    """Document in the rules collection."""
    id: str
    text: str
    category: str = "general"
    subcategory: str = ""
    source: str = "custom"
    keywords: list[str] = []
    vector: list[float] | None = None


class LoreDocument(BaseModel):
    """Document in the lore collection."""
    id: str
    text: str
    lore_type: str = "general"
    region: str = ""
    era: str = ""
    related_entity_ids: list[str] = []
    keywords: list[str] = []
    vector: list[float] | None = None


class DMStyleDocument(BaseModel):
    """Document in the DM styles collection."""
    id: str
    text: str
    style: str = "classic"
    context: str = "general"
    tone: str = "neutral"
    keywords: list[str] = []
    vector: list[float] | None = None


class ActionDocument(BaseModel):
    """Document in the actions collection."""
    id: str
    text: str
    action_type: str = "effect"
    category: str = "utility"
    base_attribute: str = ""
    keywords: list[str] = []
    vector: list[float] | None = None


class ItemDocument(BaseModel):
    """Document in the items collection."""
    id: str
    text: str
    item_type: str = "misc"
    rarity: str = "common"
    keywords: list[str] = []
    vector: list[float] | None = None


class EntityDocument(BaseModel):
    """Document in the entities collection."""
    id: str
    text: str
    entity_type: str = "creature"
    challenge_rating: float = 0.0
    creature_type: str = "humanoid"
    keywords: list[str] = []
    vector: list[float] | None = None


class SpellDocument(BaseModel):
    """Document in the spells collection."""
    id: str
    text: str
    level: int = 0
    school: str = "Evocation"
    action_type: str = "effect"
    keywords: list[str] = []
    vector: list[float] | None = None


# Map collections to document types
DOCUMENT_TYPES = {
    VectorCollection.RULES: RulesDocument,
    VectorCollection.LORE: LoreDocument,
    VectorCollection.ACTIONS: ActionDocument,
    VectorCollection.ITEMS: ItemDocument,
    VectorCollection.ENTITIES: EntityDocument,
    VectorCollection.SPELLS: SpellDocument,
}


@dataclass
class SearchResult:
    """Result from vector search."""
    id: str
    text: str
    score: float
    metadata: dict


class VectorStore:
    """
    LanceDB-based vector store for semantic search.
    
    Manages multiple collections for different content types,
    with support for filtered search and metadata queries.
    """
    
    def __init__(
        self,
        db_path: Path | str | None = None,
        embedding_dim: int = 384  # all-MiniLM-L6-v2 default
    ):
        """
        Initialize vector store.
        
        Args:
            db_path: Path to LanceDB directory. None defaults to data/vectors
            embedding_dim: Dimension of embedding vectors
        """
        if db_path is None:
            db_path = Path("data") / "vectors"
        
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        self.embedding_dim = embedding_dim
        self._db: lancedb.DBConnection | None = None
        self._embedder = None  # Lazy loaded
    
    @property
    def db(self) -> lancedb.DBConnection:
        """Get or create database connection."""
        if self._db is None:
            self._db = lancedb.connect(str(self.db_path))
        return self._db
    
    @property
    def embedder(self):
        """Lazy load the sentence transformer model."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder
    
    def embed(self, text: str | list[str]) -> list[float] | list[list[float]]:
        """
        Generate embeddings for text.
        
        Args:
            text: Single string or list of strings
            
        Returns:
            Embedding vector(s)
        """
        if isinstance(text, str):
            return self.embedder.encode(text).tolist()
        return self.embedder.encode(text).tolist()
    
    # =========================================================================
    # COLLECTION MANAGEMENT
    # =========================================================================
    
    def create_collection(
        self,
        collection: VectorCollection,
        overwrite: bool = False
    ) -> None:
        """
        Create a collection with the appropriate schema.
        
        Args:
            collection: Collection to create
            overwrite: If True, drop existing collection first
        """
        table_name = collection.value
        
        if overwrite and table_name in self.db.table_names():
            self.db.drop_table(table_name)
        
        if table_name not in self.db.table_names():
            schema = COLLECTION_SCHEMAS[collection]
            # Create empty table with schema
            self.db.create_table(table_name, schema=schema)
    
    def create_all_collections(self, overwrite: bool = False) -> None:
        """Create all defined collections."""
        for collection in VectorCollection:
            self.create_collection(collection, overwrite=overwrite)
    
    def drop_collection(self, collection: VectorCollection) -> bool:
        """Drop a collection."""
        table_name = collection.value
        if table_name in self.db.table_names():
            self.db.drop_table(table_name)
            return True
        return False
    
    def list_collections(self) -> list[str]:
        """List all collection names."""
        return self.db.table_names()
    
    def collection_exists(self, collection: VectorCollection) -> bool:
        """Check if collection exists."""
        return collection.value in self.db.table_names()
    
    def get_collection_count(self, collection: VectorCollection) -> int:
        """Get number of documents in collection."""
        if not self.collection_exists(collection):
            return 0
        table = self.db.open_table(collection.value)
        return table.count_rows()
    
    # =========================================================================
    # DOCUMENT OPERATIONS
    # =========================================================================
    
    def _prepare_document(self, doc: BaseModel, auto_embed: bool = True) -> dict:
        """Prepare document for insertion."""
        data = doc.model_dump()
        
        # Convert list fields to JSON strings
        for key in ["keywords", "related_entity_ids"]:
            if key in data and isinstance(data[key], list):
                data[key] = json.dumps(data[key])
        
        # Generate embedding if needed
        if auto_embed and (data.get("vector") is None or len(data.get("vector", [])) == 0):
            data["vector"] = self.embed(data["text"])
        
        return data
    
    def add(
        self,
        collection: VectorCollection,
        documents: BaseModel | list[BaseModel],
        auto_embed: bool = True
    ) -> int:
        """
        Add document(s) to a collection.
        
        Args:
            collection: Target collection
            documents: Single document or list of documents
            auto_embed: If True, generate embeddings automatically
            
        Returns:
            Number of documents added
        """
        if not self.collection_exists(collection):
            self.create_collection(collection)
        
        if not isinstance(documents, list):
            documents = [documents]
        
        if not documents:
            return 0
        
        # Prepare all documents
        prepared = [self._prepare_document(doc, auto_embed) for doc in documents]
        
        # Add to table
        table = self.db.open_table(collection.value)
        table.add(prepared)
        
        return len(prepared)
    
    def add_raw(
        self,
        collection: VectorCollection,
        records: list[dict],
        auto_embed: bool = True
    ) -> int:
        """
        Add raw dict records to a collection.
        
        Args:
            collection: Target collection
            records: List of dicts matching collection schema
            auto_embed: If True, generate embeddings for records missing vectors
            
        Returns:
            Number of records added
        """
        if not self.collection_exists(collection):
            self.create_collection(collection)
        
        if not records:
            return 0
        
        # Process records
        for record in records:
            # Convert list fields to JSON
            for key in ["keywords", "related_entity_ids"]:
                if key in record and isinstance(record[key], list):
                    record[key] = json.dumps(record[key])
            
            # Auto-embed if needed
            if auto_embed and (record.get("vector") is None or len(record.get("vector", [])) == 0):
                record["vector"] = self.embed(record.get("text", ""))
        
        table = self.db.open_table(collection.value)
        table.add(records)
        
        return len(records)
    
    def get(self, collection: VectorCollection, doc_id: str) -> dict | None:
        """Get a document by ID."""
        if not self.collection_exists(collection):
            return None
        
        table = self.db.open_table(collection.value)
        results = table.search().where(f"id = '{doc_id}'").limit(1).to_list()
        
        if results:
            result = results[0]
            # Parse JSON fields
            for key in ["keywords", "related_entity_ids"]:
                if key in result and isinstance(result[key], str):
                    try:
                        result[key] = json.loads(result[key])
                    except json.JSONDecodeError:
                        pass
            return result
        return None
    
    def delete(self, collection: VectorCollection, doc_id: str) -> bool:
        """Delete a document by ID."""
        if not self.collection_exists(collection):
            return False
        
        table = self.db.open_table(collection.value)
        table.delete(f"id = '{doc_id}'")
        return True
    
    def update(
        self,
        collection: VectorCollection,
        doc_id: str,
        updates: dict,
        re_embed: bool = False
    ) -> bool:
        """
        Update a document's fields.
        
        Args:
            collection: Target collection
            doc_id: Document ID
            updates: Fields to update
            re_embed: If True and text is updated, regenerate embedding
        """
        if not self.collection_exists(collection):
            return False
        
        # Get existing doc
        existing = self.get(collection, doc_id)
        if not existing:
            return False
        
        # Merge updates
        existing.update(updates)
        
        # Re-embed if needed
        if re_embed and "text" in updates:
            existing["vector"] = self.embed(existing["text"])
        
        # Delete and re-add (LanceDB doesn't have native update)
        self.delete(collection, doc_id)
        
        # Convert lists to JSON
        for key in ["keywords", "related_entity_ids"]:
            if key in existing and isinstance(existing[key], list):
                existing[key] = json.dumps(existing[key])
        
        table = self.db.open_table(collection.value)
        table.add([existing])
        
        return True
    
    # =========================================================================
    # SEARCH OPERATIONS
    # =========================================================================
    
    def search(
        self,
        collection: VectorCollection,
        query: str | list[float],
        k: int = 5,
        filter_sql: str | None = None,
        min_score: float | None = None
    ) -> list[SearchResult]:
        """
        Semantic search in a collection.
        
        Args:
            collection: Collection to search
            query: Text query or pre-computed embedding vector
            k: Number of results to return
            filter_sql: Optional SQL WHERE clause for filtering
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of SearchResult objects
        """
        if not self.collection_exists(collection):
            return []
        
        # Get query vector
        if isinstance(query, str):
            query_vector = self.embed(query)
        else:
            query_vector = query
        
        table = self.db.open_table(collection.value)
        search = table.search(query_vector).limit(k)
        
        if filter_sql:
            search = search.where(filter_sql)
        
        results = search.to_list()
        
        # Convert to SearchResult objects
        search_results = []
        for item in results:
            score = 1 - item.get("_distance", 0)  # Convert distance to similarity
            
            if min_score is not None and score < min_score:
                continue
            
            # Parse JSON fields
            metadata = {k: v for k, v in item.items() if k not in ["id", "text", "vector", "_distance"]}
            for key in ["keywords", "related_entity_ids"]:
                if key in metadata and isinstance(metadata[key], str):
                    try:
                        metadata[key] = json.loads(metadata[key])
                    except json.JSONDecodeError:
                        pass
            
            search_results.append(SearchResult(
                id=item["id"],
                text=item["text"],
                score=score,
                metadata=metadata
            ))
        
        return search_results
    
    def search_by_metadata(
        self,
        collection: VectorCollection,
        filter_sql: str,
        limit: int = 100
    ) -> list[dict]:
        """
        Search by metadata only (no vector similarity).
        
        Args:
            collection: Collection to search
            filter_sql: SQL WHERE clause
            limit: Maximum results
            
        Returns:
            List of matching documents
        """
        if not self.collection_exists(collection):
            return []
        
        table = self.db.open_table(collection.value)
        results = table.search().where(filter_sql).limit(limit).to_list()
        
        # Parse JSON fields
        for result in results:
            for key in ["keywords", "related_entity_ids"]:
                if key in result and isinstance(result[key], str):
                    try:
                        result[key] = json.loads(result[key])
                    except json.JSONDecodeError:
                        pass
        
        return results
    
    def hybrid_search(
        self,
        collection: VectorCollection,
        query: str,
        k: int = 5,
        filter_sql: str | None = None,
        keyword_boost: float = 0.3
    ) -> list[SearchResult]:
        """
        Hybrid search combining semantic and keyword matching.
        
        Args:
            collection: Collection to search
            query: Text query
            k: Number of results
            filter_sql: Optional metadata filter
            keyword_boost: Weight for keyword matches (0-1)
            
        Returns:
            List of SearchResult objects
        """
        # Get semantic results
        semantic_results = self.search(collection, query, k=k*2, filter_sql=filter_sql)
        
        # Extract keywords from query
        query_keywords = set(query.lower().split())
        
        # Re-score with keyword boost
        for result in semantic_results:
            keywords = result.metadata.get("keywords", [])
            if isinstance(keywords, str):
                try:
                    keywords = json.loads(keywords)
                except json.JSONDecodeError:
                    keywords = []
            
            keyword_matches = len(query_keywords & set(k.lower() for k in keywords))
            if keyword_matches > 0:
                result.score = result.score * (1 - keyword_boost) + keyword_boost * (keyword_matches / len(query_keywords))
        
        # Sort by adjusted score and return top k
        semantic_results.sort(key=lambda x: x.score, reverse=True)
        return semantic_results[:k]
    
    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================
    
    def search_rules(
        self,
        query: str,
        category: str | None = None,
        k: int = 5
    ) -> list[SearchResult]:
        """Search rules with optional category filter."""
        filter_sql = f"category = '{category}'" if category else None
        return self.search(VectorCollection.RULES, query, k=k, filter_sql=filter_sql)
    
    def search_lore(
        self,
        query: str,
        lore_type: str | None = None,
        region: str | None = None,
        k: int = 5
    ) -> list[SearchResult]:
        """Search lore with optional filters."""
        filters = []
        if lore_type:
            filters.append(f"lore_type = '{lore_type}'")
        if region:
            filters.append(f"region = '{region}'")
        filter_sql = " AND ".join(filters) if filters else None
        return self.search(VectorCollection.LORE, query, k=k, filter_sql=filter_sql)
    
    def get_similar_entities(
        self,
        entity_id: str,
        k: int = 5
    ) -> list[SearchResult]:
        """Find entities similar to a given entity."""
        entity = self.get(VectorCollection.ENTITIES, entity_id)
        if not entity or "vector" not in entity:
            return []
        
        results = self.search(
            VectorCollection.ENTITIES,
            entity["vector"],
            k=k+1,  # +1 because the entity itself will be returned
            filter_sql=f"id != '{entity_id}'"
        )
        return results[:k]
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> dict:
        """Get statistics for all collections."""
        stats = {}
        for collection in VectorCollection:
            if self.collection_exists(collection):
                stats[collection.value] = {
                    "count": self.get_collection_count(collection)
                }
        return stats
    
    def __repr__(self) -> str:
        collections = self.list_collections()
        return f"VectorStore(path={self.db_path}, collections={collections})"
