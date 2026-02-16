# Ontology Manager — Application Flow Design

## The Core Problem

Traditional ontology design follows a top-down path: assemble experts, define concepts, build the hierarchy, then start classifying data. This fails in practice because:

- **Nobody knows what they have.** The average mid-sized organisation has data spread across 15–40 systems, thousands of SharePoint folders, and decades of accumulated files. No single person can describe the full landscape.
- **Abstract design is paralysing.** Asking a business user "What concepts exist in your organisation?" produces either blank stares or a list so generic it's useless.
- **Perfection blocks progress.** Teams spend months debating whether a "Work Instruction" is a subtype of "OperationalDocument" or "Specification", while the actual documents sit unprocessed.
- **The ontology drifts from reality.** A top-down ontology reflects what people *think* exists, not what *actually* exists. The gap between the two is where every extraction pipeline breaks down.

## The Solution: Data-First Ontology Discovery

The application flips the approach. L1 and L2 are the scaffolding — they provide enough structure for AI to begin classifying and extracting. L3 and L4 **emerge from the data itself**, guided by the user but discovered by the system.

The fundamental insight: **you don't need to know your ontology before you process your data. You need to process your data to discover your ontology.**

```
Traditional (fails):    Design ontology → Connect data → Extract → Hope it fits

Data-first (works):     Connect data → Sample & analyse → Discover patterns →
                        Propose concepts → User reviews → Refine → Extract at scale
```

---

## Application Flow Overview

The application guides users through five phases, each building on the previous. The user can enter at any phase and loop back as understanding deepens.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   PHASE 1          PHASE 2          PHASE 3          PHASE 4            │
│   Connect          Discover         Refine           Extract            │
│                                                                         │
│   "What do you  →  "Here's what  →  "Let's make   →  "Now let's       │
│    have?"           I found"         it precise"      extract at        │
│                                                       scale"            │
│                                                                         │
│                              PHASE 5                                    │
│                              Evolve                                     │
│                                                                         │
│                              "The ontology grows                        │
│                               as new data arrives"                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Connect — "What do you have?"

### Goal

Get data into the system without requiring the user to classify anything upfront. Remove every barrier to starting.

### User Experience

The user sees a clean onboarding screen:

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   Welcome to Ontology Manager                                        │
│                                                                      │
│   Your ontology starts with 112 universal concepts that work         │
│   for any organisation. Let's discover what makes yours unique.      │
│                                                                      │
│   Connect your first data source:                                    │
│                                                                      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│   │ 📁 File      │  │ 🗄️ Database  │  │ 📧 Email     │              │
│   │    Share      │  │              │  │    / M365     │              │
│   └──────────────┘  └──────────────┘  └──────────────┘              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│   │ ☁️ SharePoint │  │ 📊 ERP      │  │ 📤 Upload    │              │
│   │              │  │    System    │  │    Files      │              │
│   └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│   Or: Upload a sample folder to get started quickly                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### What Happens

1. **User connects one or more data sources.** This can be as simple as uploading a ZIP of representative documents, or as comprehensive as connecting a SharePoint tenant, database, or ERP system.
2. **The system inventories what it finds:**
    - File types and counts (PDFs, Word docs, spreadsheets, emails, images)
    - Folder structures and naming patterns
    - Database tables and field names (for structured sources)
    - Volume estimates (how many documents, how many records)
    - Language detection (Dutch, English, German, French — critical for synonym mapping)
3. **The system takes a representative sample.** It does NOT try to process everything. It selects a diverse sample: ~50–100 documents across different folders, types, and dates. For databases, it samples ~20 rows per table with metadata (column names, types, value distributions).

### Output of Phase 1

```
┌──────────────────────────────────────────────────────────────────────┐
│  Data Source Inventory                                               │
│                                                                      │
│  📁 SharePoint - Finance                                             │
│     3,247 documents │ PDF (62%), DOCX (24%), XLSX (14%)              │
│     Languages: Dutch (71%), English (29%)                            │
│     Folders: /Facturen, /Contracten, /Rapportages, /Budget           │
│                                                                      │
│  📁 SharePoint - Operations                                          │
│     8,912 documents │ PDF (45%), DOCX (30%), MSG (15%), XLSX (10%)   │
│     Languages: Dutch (55%), English (40%), German (5%)               │
│     Folders: /Werkorders, /Specificaties, /NCRs, /Productie          │
│                                                                      │
│  🗄️ SAP ERP                                                         │
│     47 tables mapped │ 2.3M records                                  │
│     Key tables: BKPF, EKKO, MARA, LFA1, KNA1                       │
│                                                                      │
│  Sample ready: 87 documents selected for analysis                    │
│                                                                      │
│  [Start Discovery →]                                                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principle

**No classification required from the user.** The user just points the system at their data. The hard work starts with the AI, not the human.

---

## Phase 2: Discover — "Here's what I found"

### Goal

Use AI to analyse the sample data against L1+L2, identify what maps cleanly, what doesn't, and propose new concepts for L3/L4.

### What Happens

The system processes the sample in three passes:

### Pass 1: Classification against L1+L2

For each sampled document, the AI attempts classification using the existing 112 L1+L2 concepts, their synonyms, classification hints, and file patterns.

```
Sample document: /Facturen/2024/INV-2024-0847.pdf

Classification result:
  Primary concept:   Invoice          (confidence: 0.94)
  Inheritance chain:  Thing → Entity → Resource → Document →
                      FinancialDocument → Invoice
  Matched via:       synonym "factuur" in folder path,
                     classification hint "INV-" in filename,
                     document content matches Invoice properties

  Extracted properties (using Invoice template):
    document_number:  "INV-2024-0847"    (confidence: 0.98)
    vendor:           "Bosch Rexroth"     (confidence: 0.91)
    amount:           €14,520.00          (confidence: 0.95)
    currency:         "EUR"               (confidence: 0.99)
    due_date:         2024-12-15          (confidence: 0.88)
    tax_amount:       €3,049.20           (confidence: 0.92)
    purchase_order_ref: "PO-2024-0312"   (confidence: 0.85)

  ⚠ Unrecognised properties found:
    "project_code":    "PRJ-NPI-2024-07"  (not in Invoice template)
    "cost_bucket":     "R&D"              (not in Invoice template)
    "gate_reference":  "G2"               (not in Invoice template)
```

### Pass 2: Gap Analysis

After classifying all sample documents, the system identifies patterns:

- **Well-mapped concepts**: documents that classify cleanly to L2 concepts with high confidence.
- **Partial matches**: documents that fit an L2 concept but have additional properties not in the template.
- **Unmapped documents**: documents that don't match any L2 concept well.
- **Recurring extra properties**: properties that appear across multiple documents but aren't in any L2 template.
- **Naming patterns**: folder names, file naming conventions, and internal codes that suggest organisation-specific vocabulary.

### Pass 3: Concept Proposals

Based on the gap analysis, the AI proposes new concepts for L3 (industry) and L4 (organisation):

```
┌──────────────────────────────────────────────────────────────────────┐
│  Discovery Results                                                   │
│                                                                      │
│  ✅ WELL MAPPED (67 of 87 documents — 77%)                          │
│  These match existing L2 concepts with high confidence:              │
│                                                                      │
│  Invoice ×23, PurchaseOrder ×12, Contract ×8, WorkOrder ×7,         │
│  Specification ×6, Report ×5, Budget ×3, Email ×3                   │
│                                                                      │
│  ───────────────────────────────────────────────────────────────     │
│                                                                      │
│  ⚠️ PARTIAL MATCHES (14 of 87 — 16%)                                │
│  These fit an L2 concept but have extra properties:                  │
│                                                                      │
│  Invoice (7 docs) → recurring extra fields:                          │
│    • project_code (7/7), cost_bucket (7/7), gate_reference (5/7)    │
│    💡 PROPOSAL: Create "AcmeTechInvoice" extending Invoice (L4)     │
│                                                                      │
│  WorkOrder (4 docs) → recurring extra fields:                        │
│    • production_line (4/4), cycle_time (3/4), yield_rate (3/4)      │
│    💡 PROPOSAL: Create "ProductionWorkOrder" extending WorkOrder(L3) │
│                                                                      │
│  Specification (3 docs) → recurring extra fields:                    │
│    • part_number (3/3), revision (3/3), bom_reference (2/3)         │
│    💡 PROPOSAL: Create "ProductSpecification" extending Spec (L3)    │
│                                                                      │
│  ───────────────────────────────────────────────────────────────     │
│                                                                      │
│  ❌ UNMAPPED (6 of 87 — 7%)                                         │
│  These don't match any L2 concept well:                              │
│                                                                      │
│  "Stage Gate Review" (3 docs) — a multi-section evaluation doc       │
│    with gate_number, readiness_score, go/no-go decision              │
│    💡 PROPOSAL: Create "StageGateReview" as new concept under        │
│       BusinessEvent (L4)                                             │
│                                                                      │
│  "Non-Conformance Report" (2 docs) — a quality deviation report      │
│    with severity, root_cause, corrective_action, affected_batch      │
│    💡 PROPOSAL: Create "NonConformanceReport" extending              │
│       OperationalDocument (L3)                                       │
│                                                                      │
│  "Kalibratierapport" (1 doc) — a calibration certificate             │
│    with instrument, calibration_date, next_due, pass/fail            │
│    💡 PROPOSAL: Create "CalibrationReport" extending                 │
│       MeasurementRecord (L3)                                         │
│                                                                      │
│  ───────────────────────────────────────────────────────────────     │
│                                                                      │
│  📊 STRUCTURED DATA MAPPING (SAP ERP)                                │
│                                                                      │
│  Table EKKO → maps to PurchaseOrder (confidence: 0.92)               │
│    EKKO.EBELN → PurchaseOrder.po_number                              │
│    EKKO.LIFNR → PurchaseOrder.vendor (via LFA1)                     │
│    EKKO.BEDAT → PurchaseOrder.order_date                             │
│    EKKO.ZTERM → PurchaseOrder.payment_terms                          │
│    ⚠ EKKO.ZZPRJCD → unmapped (org-specific project code field)      │
│                                                                      │
│  Table LFA1 → maps to Vendor (confidence: 0.95)                     │
│  Table KNA1 → maps to Client (confidence: 0.93)                     │
│  Table MARA → maps to Product (confidence: 0.89)                    │
│    ⚠ MARA.ZZPRTNO → unmapped (custom part number field)             │
│                                                                      │
│  [Review Proposals →]                                                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principle

**Show, don't ask.** The system shows the user what it found and proposes specific concepts with specific properties. The user reviews and approves rather than designing from scratch.

---

## Phase 3: Refine — "Let's make it precise"

### Goal

Let the user review, accept, modify, or reject the AI's proposals. Build the L3/L4 ontology collaboratively.

### User Experience

Each proposal is presented as a card the user can interact with:

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  💡 Proposed Concept: AcmeTechInvoice                                │
│  Layer: L4 (Organisation)    Extends: Invoice (L2)                   │
│                                                                      │
│  Based on: 7 documents from /Facturen/ that match Invoice but        │
│  consistently include project tracking fields not in the standard    │
│  Invoice template.                                                   │
│                                                                      │
│  Proposed additional properties:                                     │
│  ┌─────────────────┬──────────┬──────────┬───────────────────────┐  │
│  │ Property        │ Type     │ Required │ Found in              │  │
│  ├─────────────────┼──────────┼──────────┼───────────────────────┤  │
│  │ project_code    │ string   │ yes      │ 7/7 docs (100%)       │  │
│  │ cost_bucket     │ enum     │ no       │ 7/7 docs (100%)       │  │
│  │ gate_reference  │ string   │ no       │ 5/7 docs (71%)        │  │
│  └─────────────────┴──────────┴──────────┴───────────────────────┘  │
│                                                                      │
│  Detected enum values for cost_bucket: R&D, Production, Overhead     │
│                                                                      │
│  Synonyms detected: "project invoice", "gate invoice"                │
│                                                                      │
│  Extraction hints: "acme", "project invoice", "PRJ-"                 │
│                                                                      │
│  Sample documents:                                                   │
│    📄 INV-2024-0847.pdf  (project_code: PRJ-NPI-2024-07)            │
│    📄 INV-2024-0923.pdf  (project_code: PRJ-NPI-2024-07)            │
│    📄 INV-2024-1105.pdf  (project_code: PRJ-MNT-2024-03)            │
│                                                                      │
│  ┌────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐          │
│  │ Accept │  │ Accept and │  │  Modify    │  │  Reject  │          │
│  │  as-is │  │ Edit first │  │  manually  │  │          │          │
│  └────────┘  └────────────┘  └────────────┘  └──────────┘          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Editing a Proposal

When the user clicks "Accept and Edit", they see a form pre-filled with the AI's suggestion:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Edit Concept: AcmeTechInvoice                                       │
│                                                                      │
│  ID:          [AcmeTechInvoice          ]                            │
│  Label:       [AcmeTech Invoice         ]                            │
│  Layer:       [L4 - AcmeTech      ▼]                                │
│  Extends:     [Invoice (L2)       ▼]  (cannot change parent layer)  │
│  Abstract:    [ ] No                                                 │
│  Description: [AcmeTech-specific invoice with project and gate     ] │
│               [tracking for NPI cost management.                   ] │
│                                                                      │
│  Synonyms:    [project invoice] [gate invoice] [+ Add]               │
│                                                                      │
│  ─── Inherited Properties (from Invoice → FinancialDocument → ───   │
│       Document → Resource → Entity → Thing) — read-only              │
│                                                                      │
│  label, description, document_date, document_type, summary,          │
│  document_number, fiscal_year, cost_centre, amount, currency ...     │
│  (25 properties inherited — click to expand)                         │
│                                                                      │
│  ─── Own Properties (new at this level) ─────────────────────────   │
│                                                                      │
│  ┌─────────────────┬──────────┬──────┬───────────────────────────┐  │
│  │ project_code    │ string   │ ☑ req│ AcmeTech project code     │  │
│  │ cost_bucket     │ enum ✏️  │ ☐ opt│ R&D, Production, Overhead │  │
│  │ gate_reference  │ string   │ ☐ opt│ Stage-gate reference      │  │
│  │ [+ Add property]                                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ─── Extraction Template ────────────────────────────────────────   │
│                                                                      │
│  Classification hints: [acme] [project invoice] [PRJ-] [+ Add]      │
│  File patterns:        [**/acme-invoices/**] [+ Add]                 │
│                                                                      │
│  [Cancel]                                     [Save to Ontology →]   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### What Happens on Save

1. The concept is written to the appropriate YAML file (L3 → `branches/manufacturing/manufacturing.yaml`, L4 → `organisation/acmetech.yaml`).
2. The compiler runs: validates references, resolves inheritance, rebuilds SQLite.
3. If validation passes, the new concept becomes immediately available for extraction.
4. If validation fails (e.g., property name collision), the user sees a clear error and suggested fix.

### Structured Data Mapping

For database sources, the user reviews the proposed field mappings:

```
┌──────────────────────────────────────────────────────────────────────┐
│  System Mapping: SAP ERP — Table EKKO                                │
│                                                                      │
│  Mapped to: PurchaseOrder (L2)                                       │
│                                                                      │
│  ┌──────────────┬──────────────────────┬────────────┬──────────┐    │
│  │ SAP Field    │ Ontology Property    │ Confidence │ Status   │    │
│  ├──────────────┼──────────────────────┼────────────┼──────────┤    │
│  │ EKKO.EBELN   │ po_number            │ 0.98       │ ✅ Auto  │    │
│  │ EKKO.LIFNR   │ vendor (via LFA1)    │ 0.95       │ ✅ Auto  │    │
│  │ EKKO.BEDAT   │ order_date           │ 0.93       │ ✅ Auto  │    │
│  │ EKKO.ZTERM   │ payment_terms        │ 0.88       │ ✅ Auto  │    │
│  │ EKKO.NETWR   │ amount               │ 0.91       │ ✅ Auto  │    │
│  │ EKKO.WAERS   │ currency             │ 0.97       │ ✅ Auto  │    │
│  │ EKKO.ZZPRJCD │ ??? (custom field)   │ —          │ ⚠️ Map   │    │
│  │              │ [project_code     ▼]  │            │          │    │
│  │ EKKO.ZZGATE  │ ??? (custom field)   │ —          │ ⚠️ Map   │    │
│  │              │ [gate_reference   ▼]  │            │          │    │
│  └──────────────┴──────────────────────┴────────────┴──────────┘    │
│                                                                      │
│  💡 The custom fields ZZPRJCD and ZZGATE match properties from       │
│     your newly created AcmeTechInvoice concept. Map them?            │
│                                                                      │
│  [Save Mapping →]                                                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principle

**The user validates, the AI proposes.** Every proposal is backed by evidence (the actual documents and data that triggered it). The user never works in the abstract — they always see real examples.

---

## Phase 4: Extract — "Now let's extract at scale"

### Goal

Run the extraction pipeline on all data using the refined ontology. Monitor results and surface issues.

### User Experience

Once the user has reviewed and accepted the proposals from Phase 3, they launch full-scale extraction:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Extraction Pipeline                                                 │
│                                                                      │
│  Ontology: AcmeTech v1.0.0 (112 base + 8 custom concepts)           │
│  Sources:  2 SharePoint libraries, 1 SAP ERP                        │
│  Scope:    12,159 documents + 2.3M database records                  │
│                                                                      │
│  ─── Progress ───────────────────────────────────────────────────   │
│                                                                      │
│  Documents:  ████████████████████░░░░░  78% (9,484 / 12,159)        │
│  DB Records: ████████████████████████▓  96% (2.21M / 2.3M)          │
│                                                                      │
│  ─── Live Classification Results ────────────────────────────────   │
│                                                                      │
│  Invoice           3,247  ██████████████████████  (34.2%)            │
│  PurchaseOrder     1,856  ████████████           (19.6%)            │
│  WorkOrder         1,203  ████████               (12.7%)            │
│  Contract            412  ███                    (4.3%)             │
│  AcmeTechInvoice     387  ██                     (4.1%)  ← L4      │
│  Specification       356  ██                     (3.8%)             │
│  Report              298  ██                     (3.1%)             │
│  ...                                                                │
│                                                                      │
│  ⚠️ Low Confidence (< 0.7):  342 documents (3.6%)                   │
│  ❌ Unclassified:             89 documents (0.9%)                    │
│                                                                      │
│  [View Low Confidence →]  [View Unclassified →]                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Handling Low Confidence and Unclassified Documents

The 89 unclassified documents become the input for the next discovery cycle. The system groups them by similarity and proposes new concepts — exactly like Phase 2, but now from edge cases rather than the full sample.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Unclassified Documents — Cluster Analysis                           │
│                                                                      │
│  Cluster 1: "Machine Logbooks" (34 docs)                             │
│    Pattern: Handwritten/scanned logbook pages with timestamps,       │
│    operator names, machine IDs, and parameter readings.              │
│    💡 Propose: MachineLogEntry extending MeasurementRecord (L3)      │
│                                                                      │
│  Cluster 2: "Customer Complaints" (22 docs)                          │
│    Pattern: Formal letters/emails from customers reporting            │
│    product defects with lot numbers and photos.                      │
│    💡 Propose: CustomerComplaint extending Ticket (L4)               │
│                                                                      │
│  Cluster 3: "Mixed/Miscellaneous" (33 docs)                          │
│    These do not form a clear cluster. Includes personal notes,       │
│    duplicate files, obsolete templates, and corrupted files.         │
│    Recommendation: Flag for manual review.                           │
│                                                                      │
│  [Review Proposals →]  [Flag for Manual Review →]                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principle

**The unclassified documents are signal, not noise.** They tell you exactly where your ontology has gaps. Every extraction run makes the ontology better.

---

## Phase 5: Evolve — "The ontology grows as new data arrives"

### Goal

The ontology is never "done". New document types appear, processes change, systems are replaced. The application monitors for drift and suggests updates.

### Continuous Monitoring

```
┌──────────────────────────────────────────────────────────────────────┐
│  Ontology Health Dashboard                                           │
│                                                                      │
│  Coverage:        96.3% of documents classified (↑ from 93.1%)       │
│  Avg Confidence:  0.89 (↑ from 0.84)                                │
│  Concepts Used:   87 of 120 (73%)                                    │
│  Last Updated:    3 days ago (v1.3.0)                                │
│                                                                      │
│  ─── Alerts ─────────────────────────────────────────────────────   │
│                                                                      │
│  🔶 New pattern detected: 12 documents in the last week match        │
│     "Invoice" but contain a new field "e-invoicing_reference"        │
│     that doesn't exist in any template. This may indicate            │
│     a regulatory change (Peppol e-invoicing).                        │
│     [Review →]                                                       │
│                                                                      │
│  🔶 Concept drift: "WorkOrder" classification confidence has          │
│     dropped from 0.91 to 0.78 over the last month. 23 recent        │
│     work orders contain fields (IoT_sensor_id, predictive_score)     │
│     suggesting a new predictive maintenance process.                 │
│     [Review →]                                                       │
│                                                                      │
│  ✅ No broken references or validation errors                        │
│  ✅ All extraction templates operational                              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### The Feedback Loop

```
New data arrives
       │
       ▼
Extract using current ontology
       │
       ├── Classified with high confidence → metadata store
       │
       ├── Classified with low confidence → flag for review
       │                                     │
       │                                     ▼
       │                              User reviews → improves extraction
       │                              template or adjusts synonyms
       │
       └── Unclassified → cluster analysis
                            │
                            ▼
                      AI proposes new concept → user reviews →
                      ontology updated → re-extract flagged docs
```

---

## The Complete Application Architecture

Putting it all together:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ONTOLOGY MANAGER APPLICATION                      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      USER INTERFACE                          │    │
│  │                                                              │    │
│  │  Onboarding  │  Discovery  │  Concept   │  Extraction │ Health│   │
│  │  Wizard      │  Explorer   │  Editor    │  Monitor    │ Dash  │   │
│  └──────┬───────┴──────┬──────┴─────┬──────┴──────┬──────┴──┬───┘   │
│         │              │            │             │         │        │
│  ┌──────▼──────────────▼────────────▼─────────────▼─────────▼───┐   │
│  │                     APPLICATION SERVICES                      │   │
│  │                                                               │   │
│  │  Data Source     Discovery      Ontology       Extraction     │   │
│  │  Connector       Engine         Compiler       Pipeline       │   │
│  │                                                               │   │
│  │  • File share    • Sample       • YAML→SQLite  • Classify     │   │
│  │  • SharePoint      selection    • Validate     • Extract      │   │
│  │  • Database      • AI classify  • Resolve      • Store        │   │
│  │  • Email/M365    • Gap analyse    inheritance  • Monitor      │   │
│  │  • Upload        • Propose      • Build index  • Alert        │   │
│  │                    concepts     • Hot-reload                   │   │
│  └──────┬───────────────┬──────────────┬──────────────┬──────────┘   │
│         │               │              │              │              │
│  ┌──────▼───────────────▼──────────────▼──────────────▼──────────┐   │
│  │                      DATA LAYER                                │   │
│  │                                                                │   │
│  │  YAML Files        Compiled        Metadata        Source      │   │
│  │  (Git repo)        Ontology        Store           Systems     │   │
│  │                    (SQLite)        (PostgreSQL)    (ERP, CRM)  │   │
│  │                                                                │   │
│  │  Schema source     Runtime         Instance        Raw data    │   │
│  │  of truth          queries         records         access      │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Why This Works Where Top-Down Fails

| Top-Down Approach | Data-First Approach |
| --- | --- |
| Requires domain experts to design upfront | Requires only a data connection to start |
| Produces an ontology that reflects theory | Produces an ontology that reflects reality |
| Takes months before first extraction | First extraction within hours (using L2) |
| Gaps discovered in production (painfully) | Gaps discovered in Phase 2 (safely) |
| Users resist because they don't understand the ontology | Users trust because they see their own data |
| Ontology maintenance is a separate project | Ontology evolves naturally from extraction feedback |
| 100% design, then 100% build | Iterative: 20% design, extract, learn, refine, repeat |

The critical psychological shift: **the ontology is not a prerequisite for extraction — it is a product of extraction.** L1+L2 provide enough structure to start. Everything else emerges.

---

## Minimum Viable Flow (Week 1)

For a first prototype, the application needs only this:

1. **Upload** — user uploads a ZIP of 50–100 representative documents.
2. **Classify** — AI classifies each document against L1+L2 concepts.
3. **Report** — show what mapped, what didn't, and what extra properties were found.
4. **Propose** — generate proposed L4 concepts for the gaps.
5. **Accept** — user accepts/edits proposals, YAML is generated.
6. **Compile** — YAML → SQLite, ontology is ready.
7. **Re-extract** — re-run extraction with the improved ontology, show the improvement.

Everything else (database connectors, continuous monitoring, health dashboard) is iteration on this core loop.