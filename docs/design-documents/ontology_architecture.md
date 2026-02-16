# Semantic Ontology Layer — Architecture Design

## 1. Problem Statement

The organisation faces three interrelated challenges:

1. **Opaque structured data** — Database tables and field names don't convey meaning (e.g., `tbl_proc_01.fld_x7` tells nothing about what it holds).
2. **Fragmented unstructured data** — Documents, emails, notes, and other content exist in many formats with no unified way to search or retrieve them contextually.
3. **No shared vocabulary** — Incoming requests use business language, but there is no bridge between that language and where the answers actually live.

The goal is to create a **semantic layer** that sits *above* all data sources and provides a unified, meaning-driven interface for discovery, search, and contextual retrieval.

---

## 2. Core Design Decision: Metadata Extraction over Vector Search

A critical architectural choice underpins this design: **unstructured data is made queryable by extracting structured metadata from it**, not by relying on vector similarity search as the primary retrieval mechanism.

### Why metadata extraction is the primary approach

| Requirement | Metadata Extraction | Vector Search |
| --- | --- | --- |
| "Invoices between Jan and Mar 2025" | Exact match on extracted dates | Cannot filter by date range |
| "Invoices where we bought Product X" | Exact match on extracted product | Approximates via similarity |
| "Contracts with value > €50k" | Exact numeric comparison | No numeric reasoning |
| Complex boolean queries | Full SQL/filter support | Limited to similarity ranking |
| Deterministic, explainable results | Yes — clear why each hit matched | No — opaque similarity score |
| Precision over recall | High precision, tuneable recall | Top-K may miss or include noise |

### When vector search adds value (optional)

Vector search remains useful as a **complement** in specific scenarios:

- **Exploratory queries** with no precise criteria ("anything related to our sustainability efforts")
- **Semantic fallback** when metadata extraction didn't capture enough detail
- **Concept discovery** ("what else is similar to this document?")
- **Natural language queries** that are vague or ambiguous by nature

The architecture supports vector search as a **pluggable, optional module** — not a dependency.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     CONSUMER LAYER                           │
│   Incoming requests · Search · AI/LLM context retrieval      │
└──────────────────────────┬───────────────────────────────────┘
                           │ queries use ontology terms
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   SEMANTIC QUERY ENGINE                       │
│   Interprets requests → resolves to ontology concepts        │
│   → builds structured queries against metadata + sources     │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌────────────────┐  ┌────────────┐  ┌────────────────────────┐
│   ONTOLOGY     │  │  MAPPING   │  │   METADATA STORE       │
│   (concepts,   │  │  REGISTRY  │  │   (extracted facts     │
│   relations,   │  │  (field →  │  │    from all sources,   │
│   properties)  │  │   concept  │  │    structured &        │
│                │  │   maps)    │  │    queryable)          │
└────────────────┘  └─────┬──────┘  └───────────┬────────────┘
                          │                     │
                          │    ┌─────────────────┤
                          │    │  ┌──────────────────────────┐
                          │    │  │  VECTOR INDEX (optional) │
                          │    │  │  (semantic similarity    │
                          │    │  │   for exploratory search)│
                          │    │  └──────────────────────────┘
                          │    │
        ┌─────────────────┼────┼────────────────┐
        ▼                 ▼    ▼                ▼
┌──────────────┐  ┌────────────┐  ┌──────────┐  ┌────────┐
│  Databases   │  │  Documents │  │  Emails  │  │  APIs  │
│ (structured) │  │  (files)   │  │  (comms) │  │        │
└──────────────┘  └────────────┘  └──────────┘  └────────┘
          DATA SOURCES (unchanged, not migrated)
```

---

## 4. Ontology Design

### 4.1 Core Ontology Structure

The ontology is organised into four pillars that together describe how the organisation works:

```
                        ┌──────────────┐
                        │ ORGANISATION │
                        │   ONTOLOGY   │
                        └──────┬───────┘
            ┌──────────┬───────┴───────┬──────────┐
            ▼          ▼               ▼          ▼
      ┌──────────┐ ┌────────┐  ┌────────────┐ ┌────────┐
      │  ENTITY  │ │PROCESS │  │  ARTIFACT  │ │ DOMAIN │
      │  PILLAR  │ │ PILLAR │  │   PILLAR   │ │ PILLAR │
      └──────────┘ └────────┘  └────────────┘ └────────┘
```

### Pillar 1 — Entity (Who / What)

Describes the actors, objects, and organisational units involved.

| Concept | Description | Examples |
| --- | --- | --- |
| `Person` | An individual (employee, customer…) | John Smith, Customer #4821 |
| `Organisation` | A company, department, team | Finance Dept, Vendor ABC |
| `Role` | A function someone performs | Approver, Project Lead |
| `Asset` | A tangible or intangible resource | Server-12, Patent #789 |
| `Product` | Something the org produces or sells | Product X, Service Plan Gold |
| `Location` | A physical or logical place | Office Brussels, Region EU-West |

### Pillar 2 — Process (How)

Describes what the organisation does, at different levels of granularity.

| Concept | Description | Examples |
| --- | --- | --- |
| `Domain` | A major business area | Procurement, HR, Finance |
| `Process` | A defined sequence of work | Purchase-to-Pay, Onboarding |
| `Activity` | A step within a process | Approve Invoice, Schedule Interview |
| `Event` | Something that triggers or results | Order Received, Contract Signed |
| `Rule` | A constraint or policy | Max approval €10k, SLA 48h |
| `Decision` | A choice point in a process | Accept/Reject, Escalate |

### Pillar 3 — Artifact (What is produced / consumed)

Describes the information objects that flow through processes.

| Concept | Description | Examples |
| --- | --- | --- |
| `Document` | A file or record | Invoice, Contract, Report |
| `DataRecord` | A row/entry in a structured system | Order line, Employee record |
| `Message` | A communication | Email, Ticket, Chat message |
| `Metric` | A measured value | Revenue Q3, SLA compliance % |
| `Reference` | Master/lookup data | Country codes, Product catalogue |

### Pillar 4 — Domain Knowledge (Context)

Describes the vocabulary and meaning specific to your business.

| Concept | Description | Examples |
| --- | --- | --- |
| `Term` | A business glossary entry | "Net Revenue", "Lead Time" |
| `Classification` | A category or tag | Priority:High, Type:Internal |
| `Status` | A lifecycle state | Draft, Active, Closed |
| `TimeFrame` | A relevant time context | FY2025, Q3, Sprint 14 |

### 4.2 Relationships Between Concepts

Relationships are as important as concepts. The ontology defines typed, directional links:

```
Person  ──── performs ────▶  Role
Role    ──── participatesIn ▶  Activity
Activity ─── partOf ────────▶  Process
Process ──── belongsTo ─────▶  Domain
Activity ─── produces ──────▶  Artifact
Activity ─── consumes ──────▶  Artifact
Activity ─── governedBy ────▶  Rule
Event   ──── triggers ──────▶  Activity
Artifact ─── relatedTo ─────▶  Term
DataRecord ─ instanceOf ────▶  Term
Document ─── associatedWith ▶  Process
```

### 4.3 Properties and Attributes

Each concept instance carries:

| Property | Purpose |
| --- | --- |
| `label` | Human-readable name |
| `description` | Plain-language explanation |
| `synonyms` | Alternative names (enables fuzzy search) |
| `sourceSystem` | Where the underlying data lives |
| `sourceReference` | How to retrieve the data (table.field, file path…) |
| `confidentiality` | Access control classification |
| `lastUpdated` | Freshness indicator |

---

## 5. The Mapping Registry

The Mapping Registry is the critical bridge between the ontology and actual data. It answers: *"For concept X, where do I find the data?"*

### 5.1 Structured Data Mapping

Each database field gets mapped to an ontology concept:

```
MAPPING ENTRY:
  source_system:    ERP_DB
  source_table:     tbl_proc_01
  source_field:     fld_x7
  ──────────────────────────────
  ontology_concept: Invoice
  ontology_property: totalAmount
  semantic_label:   "Invoice Total Amount (EUR)"
  data_type:        decimal
  unit:             EUR
  business_context: "The net total of an invoice before tax"
```

This means whenever the ontology needs "Invoice → totalAmount", it knows to query `ERP_DB.tbl_proc_01.fld_x7`.

### Mapping Table Schema

| Column | Type | Description |
| --- | --- | --- |
| `mapping_id` | UUID | Unique identifier |
| `source_system` | string | Name of the source system |
| `source_location` | string | Table, collection, file path, API endpoint |
| `source_field` | string | Column name or JSON path |
| `ontology_concept` | URI | Reference to ontology concept |
| `ontology_property` | URI | Reference to property within concept |
| `semantic_label` | string | Human-readable label |
| `transformation` | string | Optional: conversion logic |
| `confidence` | float | Quality of the mapping (0–1) |
| `validated_by` | string | Who confirmed this mapping |
| `last_reviewed` | date | When the mapping was last checked |

---

## 6. Metadata Extraction — The Heart of the Design

This is the most important section. Instead of pushing unstructured data into a vector database and relying on similarity search, we **extract structured metadata** from every unstructured source and store it in a queryable metadata store. Each unstructured source gets a **Metadata Record** that looks and behaves like structured data.

### 6.1 What is a Metadata Record?

A Metadata Record is a structured representation of the *facts* found in an unstructured source, expressed in ontology terms, with a reference back to the original source.

```
METADATA RECORD:
  record_id:          meta-2025-00482
  ─── SOURCE REFERENCE ───────────────────────────────────
  source_type:        document
  source_location:    sharepoint://finance/invoices/INV-2025-0042.pdf
  source_format:      PDF
  source_hash:        sha256:a3f8c1...  (for change detection)
  ─── ONTOLOGY CLASSIFICATION ────────────────────────────
  primary_concept:    Artifact:Invoice
  related_concepts:
    - Entity:Organisation  →  "Acme Corp" (role: vendor)
    - Entity:Product       →  "Laptop Model Z15" (role: purchased item)
    - Process:Domain       →  "Procurement"
    - Process:Process      →  "Purchase-to-Pay"
  ─── EXTRACTED PROPERTIES (structured, queryable) ───────
  properties:
    invoice_number:     "INV-2025-0042"
    invoice_date:       2025-03-15          ← queryable as date
    due_date:           2025-04-14          ← queryable as date
    total_amount:       12450.00            ← queryable as numeric
    currency:           "EUR"
    tax_amount:         2614.50
    vendor_name:        "Acme Corp"         ← queryable as text
    vendor_id:          "VND-0087"
    product_names:      ["Laptop Model Z15"] ← queryable as array
    product_codes:      ["HW-LPT-Z15"]
    purchase_order_ref: "PO-2025-1187"
    payment_terms:      "Net 30"
    cost_centre:        "IT-AMS-001"
    approver:           "Jan de Vries"
  ─── CONTENT SUMMARY ────────────────────────────────────
  summary:            "Invoice from Acme Corp for 50x Laptop Model Z15
                       for Amsterdam IT department, referencing PO-2025-1187."
  ─── QUALITY & LINEAGE ──────────────────────────────────
  extraction_method:  "LLM-assisted + rule-based"
  extraction_date:    2025-03-16
  confidence:         0.92
  reviewed_by:        null  (pending human review)
  last_verified:      null
```

### 6.2 Why This Works Better Than Vector Search for Operational Queries

With this metadata record in a queryable store, these queries become trivial:

```sql
-- "Show me all invoices between January and March 2025"
SELECT * FROM metadata_records
WHERE primary_concept = 'Artifact:Invoice'
  AND properties->>'invoice_date' BETWEEN '2025-01-01' AND '2025-03-31'

-- "Show me invoices where we bought Product X"
SELECT * FROM metadata_records
WHERE primary_concept = 'Artifact:Invoice'
  AND properties->'product_names' @> '["Product X"]'

-- "What did we buy from Acme Corp for more than €10,000?"
SELECT * FROM metadata_records
WHERE primary_concept = 'Artifact:Invoice'
  AND properties->>'vendor_name' = 'Acme Corp'
  AND (properties->>'total_amount')::numeric > 10000

-- "Find all contracts expiring in the next 90 days"
SELECT * FROM metadata_records
WHERE primary_concept = 'Artifact:Contract'
  AND (properties->>'expiry_date')::date <= CURRENT_DATE + INTERVAL '90 days'
```

Every result returns the `source_location`, so the user can always navigate to the original document.

### 6.3 The Metadata Schema (Ontology-Driven)

The ontology defines **what properties to extract** for each concept. This is the Extraction Template:

```
EXTRACTION TEMPLATE: Artifact:Invoice
  ─── Required Properties ───
  invoice_number:     type: string,  extract: always
  invoice_date:       type: date,    extract: always
  total_amount:       type: decimal, extract: always
  currency:           type: string,  extract: always
  vendor_name:        type: string,  extract: always
  ─── Optional Properties ───
  due_date:           type: date,    extract: if present
  tax_amount:         type: decimal, extract: if present
  purchase_order_ref: type: string,  extract: if present
  product_names:      type: string[], extract: if present
  payment_terms:      type: string,  extract: if present
  cost_centre:        type: string,  extract: if present
  approver:           type: string,  extract: if present
  ─── Related Entities to Resolve ───
  vendor:             resolve to → Entity:Organisation
  products:           resolve to → Entity:Product
  approver:           resolve to → Entity:Person
```

```
EXTRACTION TEMPLATE: Artifact:Contract
  ─── Required Properties ───
  contract_number:    type: string,  extract: always
  contract_type:      type: string,  extract: always  (e.g., service, supply, NDA)
  effective_date:     type: date,    extract: always
  expiry_date:        type: date,    extract: always
  parties:            type: string[], extract: always
  ─── Optional Properties ───
  total_value:        type: decimal, extract: if present
  renewal_terms:      type: string,  extract: if present
  termination_clause: type: string,  extract: if present
  sla_terms:          type: string,  extract: if present
  governing_law:      type: string,  extract: if present
  ─── Related Entities to Resolve ───
  parties:            resolve to → Entity:Organisation
  owner:              resolve to → Entity:Person
```

Each concept in the ontology has its own extraction template, so the pipeline knows what to look for.

### 6.4 Metadata Extraction Pipeline

```
                    ┌───────────────────────────────┐
                    │     SOURCE CONNECTORS          │
                    │  SharePoint, S3, Email, File   │
                    │  shares, ticketing systems     │
                    └──────────────┬────────────────┘
                                   │ raw file / message
                                   ▼
                    ┌───────────────────────────────┐
                    │  STEP 1: PARSE & EXTRACT TEXT  │
                    │  PDF → text (OCR if needed)    │
                    │  DOCX → text                   │
                    │  Email → headers + body        │
                    │  Image → OCR                   │
                    └──────────────┬────────────────┘
                                   │ plain text + source metadata
                                   ▼
                    ┌───────────────────────────────┐
                    │  STEP 2: CLASSIFY              │
                    │  "What ontology concept is     │
                    │   this document about?"        │
                    │                                │
                    │  Methods:                      │
                    │  - Rule-based (filename,       │
                    │    folder, sender, keywords)   │
                    │  - ML classifier               │
                    │  - LLM classification          │
                    │                                │
                    │  Output: primary_concept +     │
                    │          confidence score       │
                    └──────────────┬────────────────┘
                                   │ concept identified
                                   ▼
                    ┌───────────────────────────────┐
                    │  STEP 3: EXTRACT PROPERTIES    │
                    │  Load extraction template for  │
                    │  the identified concept.       │
                    │  Extract each defined property.│
                    │                                │
                    │  Methods:                      │
                    │  - Regex / pattern matching    │
                    │    (invoice numbers, dates)    │
                    │  - Named Entity Recognition    │
                    │    (companies, people, places) │
                    │  - LLM-assisted extraction     │
                    │    (complex / variable formats)│
                    │  - Table parsing               │
                    │    (line items, amounts)        │
                    │                                │
                    │  Output: property key-value    │
                    │          pairs + confidence     │
                    └──────────────┬────────────────┘
                                   │ structured properties
                                   ▼
                    ┌───────────────────────────────┐
                    │  STEP 4: RESOLVE ENTITIES      │
                    │  Match extracted names to      │
                    │  known entities in the ontology │
                    │                                │
                    │  "Acme Corp" → Entity:Org #87  │
                    │  "Jan de Vries" → Entity:Person│
                    │  "Laptop Z15" → Entity:Product │
                    │                                │
                    │  Uses: fuzzy matching, alias   │
                    │  tables, LLM disambiguation    │
                    └──────────────┬────────────────┘
                                   │ resolved references
                                   ▼
                    ┌───────────────────────────────┐
                    │  STEP 5: GENERATE SUMMARY      │
                    │  Create a concise natural-     │
                    │  language summary of the       │
                    │  document's content.           │
                    │                                │
                    │  Stored for display purposes   │
                    │  and as fallback search text.  │
                    └──────────────┬────────────────┘
                                   │ complete metadata record
                                   ▼
                    ┌───────────────────────────────┐
                    │  STEP 6: STORE & INDEX         │
                    │  Write metadata record to the  │
                    │  Metadata Store.               │
                    │  Index all queryable properties│
                    │  in the search engine.         │
                    │                                │
                    │  Optional: generate embedding  │
                    │  for vector index (if enabled) │
                    └───────────────────────────────┘
```

### 6.5 Handling Extraction Quality

Not every extraction will be perfect. The design accounts for this:

```
CONFIDENCE TIERS:
  ─────────────────────────────────────────────────────────────
  HIGH (> 0.90)    → Auto-accepted. Immediately queryable.
                     Source: rule-based extraction of standard formats,
                     or LLM extraction validated by cross-checks.

  MEDIUM (0.70–0.90)→ Queryable but flagged for review.
                     Source: LLM extraction of less structured content,
                     partial matches, ambiguous classifications.

  LOW (< 0.70)     → Stored but excluded from default queries.
                     Included only when user explicitly requests
                     "include uncertain results".
                     Queued for human review.
  ─────────────────────────────────────────────────────────────
```

Quality improvement loop:

```
Extraction with low confidence
        │
        ▼
Queued for human review
        │
        ▼
Reviewer corrects / confirms values
        │
        ├──▶ Corrected metadata saved
        │
        └──▶ Correction fed back as training data
             for future extractions of similar documents
```

### 6.6 Change Detection and Re-Extraction

Documents change. The pipeline must handle updates:

```
Source connector detects change (new hash, new modified date)
        │
        ▼
Compare source_hash with stored hash in metadata record
        │
        ├── No change → skip
        │
        └── Changed → re-run extraction pipeline
                │
                ▼
        Compare new metadata with existing record
                │
                ├── Properties unchanged → update hash + timestamp only
                │
                └── Properties changed → update record, log diff,
                                          flag for review if critical fields changed
```

---

## 7. The Metadata Store

The Metadata Store is a structured, queryable database that holds all extracted metadata records. It is the **primary search target** for operational queries.

### 7.1 Storage Design

```
┌─────────────────────────────────────────────────────────┐
│                    METADATA STORE                        │
│                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  metadata_records│  │  metadata_properties         │  │
│  │  ───────────────│  │  ────────────────────────────│  │
│  │  record_id (PK) │  │  record_id (FK)              │  │
│  │  source_type    │  │  property_key                │  │
│  │  source_location│  │  property_value_text         │  │
│  │  source_format  │  │  property_value_numeric      │  │
│  │  source_hash    │  │  property_value_date         │  │
│  │  primary_concept│  │  property_value_array (JSON) │  │
│  │  summary        │  │  confidence                  │  │
│  │  confidence     │  │  extraction_method           │  │
│  │  extraction_date│  └──────────────────────────────┘  │
│  │  reviewed_by    │                                    │
│  │  last_verified  │  ┌──────────────────────────────┐  │
│  └─────────────────┘  │  metadata_relationships      │  │
│                        │  ────────────────────────────│  │
│  ┌─────────────────┐  │  record_id (FK)              │  │
│  │  metadata_concepts│ │  related_concept             │  │
│  │  ───────────────│  │  related_entity_id           │  │
│  │  record_id (FK) │  │  relationship_type           │  │
│  │  concept_uri    │  │  confidence                  │  │
│  │  role           │  └──────────────────────────────┘  │
│  │  confidence     │                                    │
│  └─────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
```

Alternatively, using a JSONB/document approach (e.g., PostgreSQL with JSONB):

```sql
CREATE TABLE metadata_records (
    record_id           UUID PRIMARY KEY,
    -- Source reference
    source_type         VARCHAR(50) NOT NULL,
    source_location     TEXT NOT NULL,
    source_format       VARCHAR(20),
    source_hash         VARCHAR(128),
    -- Ontology classification
    primary_concept     VARCHAR(200) NOT NULL,
    related_concepts    JSONB,           -- array of {concept, role, entity_id}
    -- Extracted properties (the key queryable data)
    properties          JSONB NOT NULL,  -- {"invoice_date": "2025-03-15", "amount": 12450, ...}
    -- Content
    summary             TEXT,
    -- Quality
    confidence          NUMERIC(3,2),
    extraction_method   VARCHAR(100),
    extraction_date     TIMESTAMPTZ,
    reviewed_by         VARCHAR(200),
    last_verified       TIMESTAMPTZ,
    -- Indexing
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_primary_concept ON metadata_records (primary_concept);
CREATE INDEX idx_properties ON metadata_records USING GIN (properties);
CREATE INDEX idx_confidence ON metadata_records (confidence);
CREATE INDEX idx_source_type ON metadata_records (source_type);

-- Example: index on specific frequently-queried properties
CREATE INDEX idx_invoice_date ON metadata_records (
    (properties->>'invoice_date')
) WHERE primary_concept = 'Artifact:Invoice';

CREATE INDEX idx_vendor_name ON metadata_records (
    (properties->>'vendor_name')
) WHERE primary_concept = 'Artifact:Invoice';
```

### 7.2 Unified Query View

The power of this approach: structured source data and metadata extracted from unstructured sources can be queried **together** through the ontology.

```
┌──────────────────────────────────────────────────────┐
│              UNIFIED ONTOLOGY VIEW                    │
│                                                      │
│  Concept: Invoice                                    │
│  ┌──────────────────────────────────────────────┐    │
│  │  STRUCTURED SOURCES (via mapping registry)   │    │
│  │  ERP_DB.tbl_proc_01                          │    │
│  │    → invoice_number, date, amount, vendor…   │    │
│  │  ERP_DB.tbl_vendor                           │    │
│  │    → vendor_name, vendor_id…                 │    │
│  └──────────────────────────────────────────────┘    │
│                       +                               │
│  ┌──────────────────────────────────────────────┐    │
│  │  METADATA RECORDS (from unstructured sources)│    │
│  │  PDFs, scanned invoices, email attachments   │    │
│  │    → invoice_number, date, amount, vendor…   │    │
│  │    → SAME properties, SAME query interface   │    │
│  └──────────────────────────────────────────────┘    │
│                       =                               │
│  ┌──────────────────────────────────────────────┐    │
│  │  SINGLE QUERY SURFACE                        │    │
│  │  "Give me all invoices from Acme Corp        │    │
│  │   between Jan–Mar 2025"                      │    │
│  │  → searches BOTH structured DB + metadata    │    │
│  │    store in one operation                    │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## 8. Search Resolution Flow

When an incoming request arrives, the engine resolves it through the ontology and queries the metadata store alongside structured sources:

```
Incoming request: "What invoices did Acme Corp send us last quarter
                   for laptop purchases?"
                            │
                            ▼
              ┌─────────────────────────────┐
              │  1. INTENT PARSING          │
              │  Concepts: Invoice, Vendor  │
              │  Filters:                   │
              │    vendor = "Acme Corp"     │
              │    time = last quarter      │
              │    product contains "laptop"│
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
              │  2. ONTOLOGY RESOLUTION     │
              │  Invoice → Artifact:Invoice │
              │  Vendor → Entity:Org        │
              │  Expand synonyms:           │
              │    "Acme Corp" → also       │
              │    "ACME Corporation",      │
              │    "Acme" (VND-0087)        │
              │  Map "last quarter" →       │
              │    2025-10-01 to 2025-12-31 │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────────────────┐
              │  3. QUERY GENERATION                    │
              │                                         │
              │  Query A — Structured sources:           │
              │  SELECT * FROM erp.invoices             │
              │  WHERE vendor_id = 'VND-0087'           │
              │  AND invoice_date BETWEEN '2025-10-01'  │
              │    AND '2025-12-31'                     │
              │  AND product_description ILIKE '%laptop%'│
              │                                         │
              │  Query B — Metadata store:               │
              │  SELECT * FROM metadata_records          │
              │  WHERE primary_concept = 'Artifact:Invoice'│
              │  AND properties->>'vendor_name'          │
              │       IN ('Acme Corp','ACME Corporation')│
              │  AND (properties->>'invoice_date')::date │
              │       BETWEEN '2025-10-01' AND '2025-12-31'│
              │  AND properties->'product_names'         │
              │       @> '"laptop"'                      │
              │  AND confidence >= 0.70                  │
              │                                         │
              │  Query C — (Optional) Vector fallback:   │
              │  Only if A+B return fewer than threshold │
              │  results. Semantic search for "Acme      │
              │  laptop invoice Q4 2025".                │
              └──────────────────┬──────────────────────┘
                                 ▼
              ┌─────────────────────────────┐
              │  4. RESULT ASSEMBLY         │
              │  Merge results from A + B   │
              │  Deduplicate (same invoice   │
              │    in DB + as scanned PDF)   │
              │  Rank by:                    │
              │    1. Exact match quality    │
              │    2. Confidence score       │
              │    3. Recency                │
              │  Attach source references    │
              │  Return unified result set   │
              └─────────────────────────────┘
```

---

## 9. Vector Search as Optional Module

Vector search is **not removed** — it is repositioned as an optional, pluggable module.

### 9.1 When the Vector Module Activates

```
VECTOR SEARCH ACTIVATION RULES:
  ─────────────────────────────────────────────────────────
  1. EXPLICIT REQUEST
     User explicitly asks for "similar documents" or
     "anything related to X".

  2. FALLBACK MODE
     Primary metadata query returns 0 results.
     Engine automatically tries semantic search as backup.
     Results clearly marked as "approximate matches".

  3. EXPLORATION MODE
     User is browsing / discovering, not looking for
     specific records. e.g., "What do we know about
     sustainability in our supply chain?"

  4. DISABLED BY DEFAULT
     For operational queries with specific filters
     (dates, amounts, names), vector search is not invoked.
  ─────────────────────────────────────────────────────────
```

### 9.2 Architecture When Enabled

```
Metadata Store (primary)
        │
        │ results
        ▼
  Result set ──── enough results? ──── YES ──▶ Return
        │                                │
        NO                               │
        │                                │
        ▼                                │
  Vector Index (fallback)                │
        │                                │
        │ approximate results            │
        ▼                                │
  Merge, mark as "approximate" ──────────┘
```

### 9.3 Implementation Notes

If you choose to enable vector search:

- Embeddings are generated at the **summary** level of each metadata record, not on raw document text. This keeps the vector index small and meaningful.
- The embedding input combines: `primary_concept + summary + key property values`. This gives the embedding business context, not just language patterns.
- Vector results are always returned with lower priority than exact metadata matches.

---

## 10. Implementation Approach

### 10.1 Phased Roadmap

```
PHASE 1: Foundation (Weeks 1–6)
├── Define core ontology (concepts + relationships)
├── Build business glossary with domain experts
├── Define extraction templates for top 5–10 document types
├── Inventory all data sources (DBs, file stores, APIs)
└── Select tooling (metadata store DB, search engine, LLM for extraction)

PHASE 2: Structured Mapping (Weeks 4–10)
├── Map top-priority database fields to ontology concepts
├── Build the mapping registry
├── Create automated mapping suggestions (AI-assisted)
└── Validate mappings with data stewards

PHASE 3: Extraction Pipeline (Weeks 8–16)
├── Build source connectors (SharePoint, email, file shares)
├── Build text extraction layer (PDF, DOCX, OCR)
├── Build classification module (assign ontology concepts)
├── Build property extraction module (LLM + rules)
├── Build entity resolution module
├── Build metadata store + indexes
└── Process initial batch of historical documents

PHASE 4: Query Engine (Weeks 14–20)
├── Build semantic query resolver (intent → ontology → queries)
├── Build unified query that spans structured DB + metadata store
├── Build result assembly + deduplication
├── Build API layer for consumers (search, LLM context)
├── Optional: add vector search fallback module
└── Test with real incoming requests

PHASE 5: Operationalise (Weeks 18–24)
├── Governance: who maintains ontology + reviews extractions?
├── Automation: new documents auto-extracted on arrival
├── Monitoring: extraction quality, query coverage, result relevance
├── Feedback loop: users flag bad results → improve pipeline
└── Expand to additional document types + data sources
```

### 10.2 Technology Stack Considerations

| Component | Options | Role |
| --- | --- | --- |
| Ontology store | Neo4j, Amazon Neptune, Apache Jena, Protégé (OWL) | Store concepts + relationships |
| Mapping registry | PostgreSQL, dedicated metadata catalog | Store field → concept maps |
| **Metadata store** | **PostgreSQL (JSONB), Elasticsearch, MongoDB** | **Primary query target** |
| Search engine | Elasticsearch, OpenSearch | Full-text + faceted search |
| Extraction pipeline | Apache Airflow, Prefect, custom Python | Orchestrate extraction jobs |
| LLM for extraction | Claude API, local models | Classification + extraction |
| Entity resolution | Custom matching service, dedupe library | Link names to known entities |
| Vector database (opt.) | Pinecone, Weaviate, Qdrant, pgvector | Optional semantic fallback |
| API gateway | FastAPI, Kong, AWS API Gateway | Expose unified search API |

### 10.3 Ontology Serialisation Format

- **OWL/RDF** — If you want standards-compliant, interoperable (W3C standard)
- **JSON-LD** — Lightweight, developer-friendly, embeddable
- **Property Graph** — If using Neo4j or similar (nodes + edges + properties)
- **YAML/JSON** — Simplest, good for early prototyping

Recommended: **start with YAML/JSON for rapid iteration**, then migrate to OWL or a graph database when the model stabilises.

---

## 11. Governance Model

### 11.1 Roles

| Role | Responsibility |
| --- | --- |
| Ontology Owner | Overall accountability, resolves disputes |
| Domain Stewards | Maintain concepts + extraction templates for their domain |
| Data Stewards | Maintain field-to-concept mappings for their systems |
| Extraction Reviewers | Review and correct low/medium-confidence extractions |
| Search/AI Team | Maintain pipeline, metadata store, query engine |
| All Users | Flag incorrect results; suggest new terms |

### 11.2 Change Process

```
Propose change (new concept, new mapping, new extraction template)
        │
        ▼
Review by Domain Steward
        │
        ├── Minor (add synonym, fix description) → Auto-approve
        │
        ├── Standard (new concept, new mapping, new template) → Steward approves
        │
        └── Major (restructure pillar, merge concepts) → Ontology Owner + committee
```

### 11.3 Quality Metrics

| Metric | Target | Measures |
| --- | --- | --- |
| Mapping coverage | > 80% | % of active DB fields mapped |
| Extraction coverage | > 70% | % of documents with metadata records |
| Extraction accuracy | > 85% | % of extracted properties confirmed correct |
| Query completeness | > 75% | % of queries returning results from both |
|  |  | structured + unstructured sources |
| Freshness | < 7 days | Time since last mapping/extraction review |
| User satisfaction | > 4/5 | Self-reported usefulness of results |

---

## 12. Example Walkthrough

### Scenario: Processing an incoming purchase request

**Request:** *"We need to order 50 laptops for the Amsterdam office. What's our current contract with Dell and what's the approval process for orders above €25k?"*

**Step 1 — Intent Parsing (via LLM + ontology)**

```
Detected concepts:
  - Product: Laptop
  - Entity/Location: Amsterdam Office
  - Entity/Organisation: Dell
  - Artifact: Contract
  - Process: Procurement / Purchase Approval
  - Rule: Approval threshold (€25k)
```

**Step 2 — Query Generation**

```
Query A — Structured (contracts DB):
  SELECT * FROM contracts
  WHERE vendor_name ILIKE '%Dell%' AND status = 'Active'

Query B — Metadata store (contract documents):
  SELECT * FROM metadata_records
  WHERE primary_concept = 'Artifact:Contract'
    AND properties->>'parties' ILIKE '%Dell%'
    AND confidence >= 0.70

Query C — Metadata store (approval policies):
  SELECT * FROM metadata_records
  WHERE primary_concept IN ('Process:PurchaseApproval', 'Rule:ApprovalThreshold')
    AND (properties->>'threshold_amount')::numeric <= 25000

Query D — Structured (procurement rules):
  SELECT * FROM erp.approval_rules
  WHERE threshold_eur <= 25000
```

**Step 3 — Result Assembly**

```
Assembled context:
  FROM STRUCTURED DB:
  - 1 active Dell framework contract (ref: CTR-2024-0115)
  - Approval rule: orders > €25k require VP + Finance Director

  FROM METADATA STORE (extracted from documents):
  - Dell Framework Agreement PDF (CTR-2024-0115)
    → pricing tier: €980/unit for >25 laptops
    → valid until: 2026-06-30
    → account manager: Sarah Johnson
    → source: sharepoint://procurement/contracts/Dell-2024.pdf
  - Purchase Approval Policy v3.2
    → >€25k: VP approval + Finance Director sign-off
    → >€50k: Board approval required
    → source: sharepoint://policies/procurement/approval-policy-v3.2.pdf
  - Previous laptop order from Dell (March 2025)
    → 30 units, €29,400, approved by M. Bakker
    → source: sharepoint://procurement/orders/PO-2025-1187.pdf

Total: 1 structured DB record, 3 document-sourced metadata records
       each with a direct link to the original document.
```

---

## 13. Key Design Principles

1. **Data stays in place** — The ontology is a layer, not a new database. Don't migrate data; map it and extract metadata from it.
2. **Extracted metadata is the bridge** — Unstructured data becomes queryable not through similarity matching, but through structured metadata extraction. The metadata store speaks the same language as your databases.
3. **Start with the questions** — Build the ontology and extraction templates around the requests people actually make, not around the data you happen to have.
4. **Good enough beats perfect** — A 70% complete ontology that's live is more valuable than a 100% complete one that's still in design.
5. **Synonyms are essential** — People say "bill", "invoice", "factuur", "Rechnung". The ontology must understand all of them.
6. **Confidence scores everywhere** — Every mapping and extraction should carry a confidence score. This lets you improve iteratively and filter low-quality matches.
7. **Human-in-the-loop** — AI extracts, humans validate. Especially in early phases, review queues for medium/low-confidence extractions are critical.
8. **Feedback-driven** — Every search result should have a "was this helpful?" mechanism that feeds back into improving extractions and rankings.
9. **Vector search is a complement, not a foundation** — Use it for exploration and fallback, not for operational queries that need precision.