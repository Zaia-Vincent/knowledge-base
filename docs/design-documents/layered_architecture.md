# — Foundation Design

## 1. Design Philosophy: Ontologies as Inheritance Hierarchies

The research is clear on one thing: the most successful ontology ecosystems in the world — from biomedical (OBO Foundry), to defense (DOD/IC), to manufacturing (IOF), to finance (FIBO) — all follow the same layered inheritance pattern. This design adopts that pattern and adapts it for enterprise process ontologies.

### 1.1 Lessons from Established Ontology Ecosystems

| Ecosystem | Upper Layer | Mid-Level Layer | Domain Layer | Adopted by |
| --- | --- | --- | --- | --- |
| **BFO + CCO** | BFO (ISO 21838-2) | Common Core Ontologies (11 modules) | Mission-specific extensions | US DOD, Intelligence Community |
| **IOF** | BFO | IOF Core | Supply Chain, Maintenance, etc. | Manufacturing industry (NIST) |
| **FIBO** | — | FIBO Foundations | Securities, Derivatives, Entities | Financial industry (OMG/EDMC) |
| **OBO Foundry** | BFO | OBI, IAO | Gene Ontology, Cell Ontology, etc. | 650+ biomedical projects |
| **Schema.org** | Thing | CreativeWork, Event, Organization | Industry extensions | Google, Microsoft, Yahoo, Yandex |

The common pattern is unmistakable:

```
ABSTRACT (stable, rarely changes)
    │
    ▼
GENERIC (common across industries)
    │
    ▼
INDUSTRY-SPECIFIC (shared within a sector)
    │
    ▼
ORGANISATION-SPECIFIC (your unique processes)
```

This mirrors the OO inheritance principle: **define once at the most general level, specialise downward, inherit upward.** Child concepts automatically inherit all properties and relationships from their parents.

### 1.2 Core OO Principles Applied to Ontology Design

| OO Principle | Ontology Equivalent | Example |
| --- | --- | --- |
| **Class** | Concept | `Invoice`, `Contract`, `Employee` |
| **Inheritance (subClassOf)** | Specialisation | `PurchaseInvoice` extends `Invoice` |
| **Property inheritance** | Slot/attribute inheritance | `PurchaseInvoice` inherits `invoice_date`, `amount`, `vendor` from `Invoice` |
| **Abstract class** | Non-instantiable concept | `FinancialDocument` — never used directly, only through subclasses |
| **Interface / mixin** | Cross-cutting property set | `Auditable` — adds `audit_trail`, `last_audited_by` to any concept |
| **Polymorphism / substitution** | Liskov-like substitution | A query for `Invoice` also returns `PurchaseInvoice`, `CreditNote`, etc. |
| **Override** | Property refinement | `Invoice.amount` is optional; `PurchaseInvoice.amount` is required |
| **Composition** | Part-of relationship | `OrderLine` is part of `PurchaseOrder` |
| **Encapsulation** | Extraction template scoping | Each concept defines its own extractable properties |

### 1.3 The Substitution Principle in Practice

This is the most practically important OO principle for search. When a concept hierarchy is correctly built:

```
Query: "Find all FinancialDocuments from Acme Corp"

FinancialDocument (abstract)
├── Invoice
│   ├── PurchaseInvoice     ← included in results
│   ├── SalesInvoice        ← included in results
│   └── CreditNote          ← included in results
├── Contract
│   ├── ServiceContract     ← included in results
│   ├── SupplyContract      ← included in results
│   └── NDA                 ← included in results
└── Receipt                 ← included in results

All subtypes are valid substitutes for the parent type.
The query automatically expands to include all descendants.
```

---

## 2. The Four-Layer Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 4: ORGANISATION ONTOLOGY                                  │
│  Your unique concepts, processes, vocabulary, and extensions      │
│  e.g., "Stage-Gate Review", "NPI Process", "Customer Tier A"     │
│                                                                  │
│  Extends Layer 3 (or Layer 2 if no branch applies)               │
└──────────────────────────────┬───────────────────────────────────┘
                               │ extends / specialises
┌──────────────────────────────┴───────────────────────────────────┐
│  LAYER 3: BRANCH ONTOLOGY (industry-specific)                    │
│  Predefined per industry sector                                  │
│  e.g., Manufacturing, Financial Services, Healthcare, Retail,    │
│        Professional Services, Public Sector, Logistics           │
│                                                                  │
│  Extends Layer 2                                                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │ extends / specialises
┌──────────────────────────────┴───────────────────────────────────┐
│  LAYER 2: UNIVERSAL ENTERPRISE ONTOLOGY (cross-industry)         │
│  Common business concepts shared across ALL organisations        │
│  e.g., Invoice, Contract, Employee, Purchase Order, Project      │
│                                                                  │
│  Extends Layer 1                                                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │ extends / specialises
┌──────────────────────────────┴───────────────────────────────────┐
│  LAYER 1: FOUNDATIONAL ONTOLOGY (abstract, domain-neutral)       │
│  Most generic categories: Entity, Process, Artifact, Quality     │
│  Inspired by BFO/CCO but simplified for enterprise use           │
│                                                                  │
│  Stable. Rarely changes. Provides the "grammar" of the ontology. │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 Design Rules Across Layers

| Rule | Description |
| --- | --- |
| **Downward specialisation only** | A child class may only be a subclass of a class in the same or higher layer. Never upward. |
| **Property inheritance** | A child inherits ALL properties from its parent. It may add new properties or refine inherited ones (make optional → required, narrow value types). |
| **No property removal** | A child may NOT remove an inherited property. If `Invoice` has `amount`, every subtype of `Invoice` has `amount`. |
| **Extraction template inheritance** | When a concept has an extraction template, subtypes inherit it and may extend it with additional fields. |
| **Relationship inheritance** | If `Artifact` has a relationship `producedBy → Activity`, then `Invoice` (a subtype of `Artifact`) also has `producedBy → Activity`. |
| **Open-world extension** | Any layer can add new concepts, properties, and relationships. It cannot modify or contradict higher layers. |
| **Synonym accumulation** | Subtypes inherit all parent synonyms and may add their own. `PurchaseInvoice` inherits synonyms of `Invoice` ("bill", "factuur") and adds its own ("inkoopfactuur"). |

---

## 3. Layer 1 — Foundational Ontology

This is the "grammar" of the ontology. It defines the most abstract categories that everything else specialises from. It is inspired by BFO (ISO standard) and the Common Core Ontologies, but simplified for practical enterprise use. It should almost never need to change.

### 3.1 Top-Level Taxonomy

Layer 1 uses plain-language names that any business user can understand. Each concept carries a `formal_equivalent` annotation referencing the BFO/CCO term it aligns with, preserving the option of formal interoperability without burdening daily users.

```
Thing
├── Entity (things that exist and persist through time)
│   │                                    [BFO: Continuant]
│   │
│   ├── Actor (people and organisations that can act)
│   │   │                                [BFO: Agent]
│   │   ├── Person
│   │   └── Organisation
│   │
│   ├── Object (tangible objects that do not act)
│   │   │                                [BFO: MaterialEntity]
│   │   ├── Asset
│   │   ├── Product
│   │   └── Facility
│   │
│   ├── Place (spatial regions)
│   │                                    [BFO: Site]
│   │
│   ├── Characteristic (qualities and measures of a thing)
│   │   │                                [BFO: Quality]
│   │   ├── Quantity (measurable value)
│   │   └── Status (lifecycle state)
│   │
│   ├── Role (contextual function someone or something plays)
│   │                                    [BFO: Role]
│   │
│   └── Resource (content that can be recorded)
│       │                                [BFO: InformationContentEntity / IAO]
│       ├── Document
│       ├── DataRecord
│       ├── Message
│       └── Identifier
│
├── Activity (things that happen over time)
│   │                                    [BFO: Occurrent → Process]
│   ├── Process (a sequence of steps)
│   ├── Task (an atomic unit of work)
│   └── Event (a noteworthy occurrence)
│
├── TimePeriod (a span of time)
│                                        [BFO: TemporalRegion]
│
└── State (a condition that holds during a period)
                                         [BFO: State]
```

**Naming principles for Layer 1:**

| Principle | Explanation |
| --- | --- |
| **Plain language first** | A domain steward should understand every concept without a glossary. |
| **BFO alignment preserved** | Each concept carries a `formal_equivalent` annotation for interoperability. |
| **No jargon at the root** | Terms like "Continuant", "Occurrent", "IndependentContinuant" are replaced. They add cognitive load without practical value for enterprise use. |
| **Grouping by intent** | `Actor` groups who-can-act; `Object` groups what-exists-but-doesn't-act; `Activity` groups what-happens. These map directly to the questions users ask. |

### 3.2 Foundational Properties (inherited by everything)

| Property | Type | Applies to | Description |
| --- | --- | --- | --- |
| `label` | string | Thing | Human-readable name |
| `description` | string | Thing | Plain-language explanation |
| `synonyms` | string[] | Thing | Alternative names |
| `identifier` | Identifier | Thing | Unique reference |

### 3.3 Foundational Relationships

```
# ─── Actor relationships (only Actors can act) ─────
Actor         ── participatesIn ──▶  Activity
Actor         ── hasRole ──────────▶  Role

# ─── Object relationships ─────────────────────
Object ── locatedIn ────────▶  Place
Object ── ownedBy ──────────▶  Actor

# ─── Activity relationships ──────────────────────────
Activity      ── hasInput ─────────▶  Thing
Activity      ── hasOutput ────────▶  Thing
Activity      ── hasPart ──────────▶  Activity
Activity      ── occursAt ─────────▶  TimePeriod
Activity      ── occursIn ─────────▶  Place

# ─── General relationships ───────────────────────────
Thing         ── hasPart ──────────▶  Thing
Thing         ── hasCharacteristic ─▶  Characteristic
Resource ── isAbout ──────▶  Thing
Resource ── createdBy ────▶  Actor
Entity        ── involvedIn ───────▶  Activity
```

### 3.4 Cross-Cutting Property Sets (Mixins)

These are reusable property bundles that can be applied to any concept across all layers:

```
┌──────────────────────────────────────────────────────┐
│  «mixin» Trackable                                    │
│  ─────────────────                                    │
│  created_date:    date                                │
│  created_by:      Actor                               │
│  modified_date:   date                                │
│  modified_by:     Actor                               │
│  version:         integer                             │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  «mixin» Classifiable                                 │
│  ────────────────────                                 │
│  categories:      Classification[]                    │
│  tags:            string[]                            │
│  status:          Status                              │
│  priority:        Priority                            │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  «mixin» Auditable                                    │
│  ─────────────────                                    │
│  audit_trail:     AuditEntry[]                        │
│  last_audited_by: Actor                               │
│  last_audited_on: date                                │
│  compliance_status: string                            │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  «mixin» Locatable                                    │
│  ────────────────                                     │
│  location:        Place                               │
│  region:          string                              │
│  country:         string                              │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  «mixin» HasMonetaryValue                             │
│  ────────────────────────                             │
│  amount:          decimal                             │
│  currency:        Currency                            │
│  exchange_rate:   decimal (optional)                  │
│  amount_base_currency: decimal (optional)             │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  «mixin» SourceMapped                                 │
│  ─────────────────                                    │
│  source_system:   string                              │
│  source_location: string                              │
│  source_reference:string                              │
│  confidence:      float                               │
│  extraction_method: string                            │
└──────────────────────────────────────────────────────┘
```

---

## 4. Layer 2 — Universal Enterprise Ontology

This layer contains concepts that are common to virtually every organisation, regardless of industry. It is the workhorse layer — most queries will resolve to concepts defined here.

### 4.1 Entity Pillar (Who / What)

The Entity Pillar answers "Who is involved?" and "What things exist?" Its root is `Entity` from Layer 1 — things that exist and persist through time. Beneath it, `Actor` and `Object` are **siblings**, not parent-child. This distinction matters: Actors can act intentionally (people, organisations); Objects cannot (products, assets, buildings). A query for "all Actors in this process" correctly returns people and organisations — but not products or warehouses.

```
Entity (from Layer 1)
│
├── Actor (people and organisations that can act)
│   ├── Person
│   │   ├── Employee
│   │   ├── Customer
│   │   ├── SupplierContact
│   │   └── ExternalStakeholder
│   └── Organisation
│       ├── InternalOrganisation
│       │   ├── Department
│       │   ├── Team
│       │   └── BusinessUnit
│       ├── ExternalOrganisation
│       │   ├── Vendor
│       │   ├── Client
│       │   ├── Partner
│       │   └── RegulatoryBody
│       └── LegalEntity
│
├── Object (tangible things — NOT actors, cannot act)
│   ├── Asset
│   │   ├── PhysicalAsset
│   │   └── DigitalAsset
│   ├── Product
│   │   ├── Good
│   │   └── Service
│   └── Facility
│       ├── Office
│       ├── Warehouse
│       └── Site
│
└── Place (spatial regions)
    ├── PhysicalPlace
    ├── Region
    └── VirtualPlace

Role (from Layer 1 — a Characteristic, not an Entity)
├── JobRole
├── ProcessRole (Approver, Reviewer, Owner)
└── ProjectRole (Lead, Member, Sponsor)
```

**Why this separation matters for queries:**

| Query | Resolves to | Does NOT include |
| --- | --- | --- |
| "Who is involved in this process?" | Actor → Person, Organisation | Product, Asset, Facility |
| "What assets are at the Amsterdam office?" | Object → Asset | Person, Organisation |
| "What entities does this contract reference?" | Entity → all | (broadest scope) |
| "Which vendors supplied this product?" | Actor → Organisation → Vendor | Product (the thing supplied) |

### Entity Properties

```yaml
# ─── Actor branch (Who) ─────────────────────────────────

Person:
  inherits: Actor
  mixins: [Trackable, Locatable]
  properties:
    given_name:     { type: string, required: true }
    family_name:    { type: string, required: true }
    email:          { type: string }
    phone:          { type: string }
    job_title:      { type: string }
    department:     { type: Department }
    reports_to:     { type: Person }

Employee:
  inherits: Person
  additional_properties:
    employee_id:    { type: string, required: true }
    hire_date:      { type: date }
    employment_type:{ type: enum[FullTime, PartTime, Contractor, Temporary] }
    cost_centre:    { type: string }

Organisation:
  inherits: Actor
  mixins: [Trackable, Locatable]
  properties:
    legal_name:     { type: string, required: true }
    trade_name:     { type: string }
    registration_number: { type: string }
    website:        { type: url }
    industry:       { type: string }

Vendor:
  inherits: ExternalOrganisation
  additional_properties:
    vendor_id:      { type: string, required: true }
    payment_terms:  { type: string }
    approved:       { type: boolean }
    rating:         { type: decimal }
    primary_contact:{ type: Person }

# ─── Object branch (What) ────────────────────────
# These inherit from Object, NOT from Actor.
# They are things that exist but do not act intentionally.

Product:
  inherits: Object
  mixins: [Trackable, Classifiable]
  properties:
    product_name:   { type: string, required: true }
    product_code:   { type: string }
    category:       { type: Classification }
    unit_price:     { type: decimal }
    unit_of_measure:{ type: string }
    active:         { type: boolean, default: true }

Asset:
  inherits: Object
  mixins: [Trackable, Locatable, Auditable]
  properties:
    asset_tag:      { type: string, required: true }
    asset_type:     { type: enum[Physical, Digital] }
    acquisition_date:{ type: date }
    book_value:     { type: decimal }
    assigned_to:    { type: Person }
    condition:      { type: enum[New, Good, Fair, Poor, Decommissioned] }

Facility:
  inherits: Object
  mixins: [Trackable, Locatable]
  properties:
    facility_name:  { type: string, required: true }
    facility_type:  { type: enum[Office, Warehouse, Site, Factory, Lab] }
    capacity:       { type: integer }
    managed_by:     { type: Person }
    parent_facility:{ type: Facility }
```

### 4.2 Process Pillar (How)

```
Process (from Layer 1)
├── BusinessProcess
│   ├── OperationalProcess
│   ├── SupportProcess
│   └── ManagementProcess
├── Activity (a step within a process)
│   ├── ApprovalActivity
│   ├── ReviewActivity
│   ├── TransformationActivity
│   └── CommunicationActivity
├── Project
│   ├── InternalProject
│   └── ClientProject
└── Task (an atomic work item)

Event (from Layer 1)
├── BusinessEvent
│   ├── TransactionEvent
│   ├── MilestoneEvent
│   ├── EscalationEvent
│   └── ComplianceEvent

State (from Layer 1)
├── ProcessState
│   ├── Draft
│   ├── InProgress
│   ├── PendingApproval
│   ├── Approved
│   ├── Rejected
│   ├── Completed
│   └── Cancelled
```

### Process Properties

```yaml
BusinessProcess:
  inherits: Process
  mixins: [Trackable, Classifiable]
  properties:
    process_id:     { type: string, required: true }
    process_name:   { type: string, required: true }
    domain:         { type: BusinessDomain }
    owner:          { type: Person }
    sla_hours:      { type: integer }
    activities:     { type: Activity[], relationship: hasPart }
    inputs:         { type: Thing[], relationship: hasInput }
    outputs:        { type: Thing[], relationship: hasOutput }

Activity:
  inherits: Process
  additional_properties:
    sequence_number:{ type: integer }
    responsible:    { type: Role }
    duration_hours: { type: decimal }
    is_automated:   { type: boolean }
    predecessor:    { type: Activity }
    successor:      { type: Activity }

ApprovalActivity:
  inherits: Activity
  additional_properties:
    approval_threshold: { type: decimal }
    threshold_currency: { type: Currency }
    required_role:  { type: Role }
    escalation_after_hours: { type: integer }

Project:
  inherits: Process
  mixins: [HasMonetaryValue]
  additional_properties:
    project_code:   { type: string, required: true }
    start_date:     { type: date }
    end_date:       { type: date }
    budget:         { type: decimal }
    sponsor:        { type: Person }
    status:         { type: ProcessState }
```

### 4.3 Artifact Pillar (What is produced / consumed)

```
Document (from Layer 1, under Resource)
├── FinancialDocument (abstract)
│   ├── Invoice
│   ├── CreditNote
│   ├── Receipt
│   ├── Budget
│   └── FinancialReport
├── LegalDocument (abstract)
│   ├── Contract
│   ├── Agreement
│   ├── Policy
│   └── Regulation
├── OperationalDocument (abstract)
│   ├── PurchaseOrder
│   ├── SalesOrder
│   ├── WorkOrder
│   ├── Specification
│   └── Report
├── HRDocument (abstract)
│   ├── JobDescription
│   ├── PerformanceReview
│   ├── LeaveRequest
│   └── PaySlip

DataRecord (from Layer 1)
├── TransactionRecord
├── MasterDataRecord
├── LogEntry
└── MeasurementRecord

Message (from Layer 1)
├── Email
├── Ticket
├── Notification
└── ChatMessage
```

### Artifact Properties (with inheritance)

```yaml
# ─── Abstract parent ───────────────────────────────────────
FinancialDocument:
  inherits: Document
  abstract: true    # never instantiated directly
  mixins: [Trackable, Auditable, HasMonetaryValue, SourceMapped]
  properties:
    document_number: { type: string, required: true }
    document_date:   { type: date, required: true }
    fiscal_year:     { type: string }
    cost_centre:     { type: string }
    related_party:   { type: Organisation }

# ─── Concrete child ────────────────────────────────────────
Invoice:
  inherits: FinancialDocument    # gets ALL properties above
  properties:                    # ADDITIONAL properties only
    invoice_type:    { type: enum[Standard, Proforma, Recurring] }
    due_date:        { type: date }
    payment_terms:   { type: string }
    vendor:          { type: Vendor, required: true }
    line_items:      { type: InvoiceLineItem[] }
    tax_amount:      { type: decimal }
    purchase_order_ref: { type: PurchaseOrder }
  synonyms: [bill, factuur, Rechnung, facture, factura]

# ─── Concrete child of Invoice (deeper specialisation) ─────
# This is where Branch or Organisation layers typically add
# their specialisations. See Section 5.
```

### 4.4 Domain Knowledge Pillar (Context / Vocabulary)

```
Characteristic (from Layer 1)
├── Quantity (measurable value)
│   ├── MonetaryAmount
│   ├── Duration
│   ├── Percentage
│   └── Count
├── Status (lifecycle state)

Classification (new)
├── BusinessDomain (Procurement, HR, Finance, Sales, IT, etc.)
├── DocumentType
├── Priority (Low, Medium, High, Critical)
├── Confidentiality (Public, Internal, Confidential, Restricted)

Identifier (from Layer 1, under Resource)
├── InternalIdentifier
├── ExternalIdentifier (VAT number, DUNS, LEI, etc.)
├── ReferenceCode
```

### 4.5 Universal Relationships

These relationships are defined at Layer 2 and inherited by all specialisations:

```
# ─── Actor-specific (only actors) ────────────────────
Organisation ── employs ──────────▶  Person
Person       ── holdsRole ────────▶  Role
Role         ── participatesIn ───▶  Activity

# ─── Object-specific ──────────────────────────
Asset        ── assignedTo ───────▶  Person
Asset        ── locatedAt ────────▶  Facility
Product      ── suppliedBy ───────▶  Vendor
Facility     ── managedBy ────────▶  Person

# ─── Process relationships ───────────────────────────
Activity     ── partOf ───────────▶  BusinessProcess
BusinessProcess ── belongsTo ─────▶  BusinessDomain
Activity     ── produces ─────────▶  Document
Activity     ── consumes ─────────▶  Document
Activity     ── governedBy ───────▶  Policy
Event        ── triggers ─────────▶  Activity

# ─── Artifact relationships ──────────────────────────
Document     ── relatedTo ────────▶  Document
Document     ── references ───────▶  DataRecord
Invoice      ── paidVia ──────────▶  TransactionRecord
Invoice      ── issuedBy ─────────▶  Organisation
Contract     ── governs ──────────▶  BusinessProcess
Contract     ── hasContractingParty▶  Organisation
PurchaseOrder── fulfilledBy ──────▶  Invoice
PurchaseOrder── ordersProduct ────▶  Product
```

---

## 5. Layer 3 — Branch Ontologies (Industry-Specific)

Branch ontologies specialise the Universal Enterprise Ontology for specific industries. They add concepts, properties, and relationships that are meaningful within that sector but not universally.

### 5.1 Which Branches?

Based on the research and common industry classifications, the following branch ontologies should be developed as needed:

| Branch | Focus | Existing reference ontologies |
| --- | --- | --- |
| **Manufacturing** | Production, BOM, quality control, supply chain | IOF Core, CDM-Core, InPro |
| **Financial Services** | Instruments, compliance, trading, risk | FIBO, LKIF, FinRegOnt |
| **Healthcare** | Patients, clinical, treatment, devices | SNOMED CT, HL7 FHIR, OBI |
| **Retail & Distribution** | Merchandising, POS, fulfilment, returns | GS1, schema.org/Product |
| **Professional Services** | Engagements, billing, resource management | — (underserved, custom) |
| **Public Sector / Government** | Legislation, licensing, citizen services | LKIF, org ontology (W3C) |
| **Logistics & Transport** | Shipping, routing, customs, fleet | SCRO (IOF), GS1, UN/CEFACT |
| **Construction & Engineering** | Projects, BIM, permits, safety | IFC/buildingSMART, ISO 15926 |
| **IT & Telecommunications** | ITIL, incidents, SLAs, infrastructure | IT-CMF, ITIL ontology |

**You do not need all of these.** Start with the one branch that matches your organisation. The architecture allows adding more later without breaking anything.

### 5.2 Example: Manufacturing Branch Ontology

This extends Layer 2 by adding manufacturing-specific specialisations:

```
# ─── Entity extensions (Object branch) ─────────────
# Inheritance chain: Entity → Object → Product
Product (from Layer 2)
├── ManufacturedProduct
│   ├── FinishedGood
│   ├── SemiFinishedGood
│   └── RawMaterial
├── Component
└── SparePart

# Inheritance chain: Entity → Object → Asset
Asset (from Layer 2)
├── ProductionEquipment
│   ├── Machine
│   ├── ToolingFixture
│   └── MeasuringInstrument
├── ProductionLine

# Inheritance chain: Entity → Object → Facility
Facility (from Layer 2)
├── ProductionFacility
│   ├── Shopfloor
│   ├── CleanRoom
│   └── TestLab

# ─── Process extensions ─────────────────────────────────
BusinessProcess (from Layer 2)
├── ProductionProcess
│   ├── AssemblyProcess
│   ├── MachiningProcess
│   ├── QualityInspection
│   └── PackagingProcess
├── MaintenanceProcess
│   ├── PreventiveMaintenance
│   ├── CorrectiveMaintenance
│   └── PredictiveMaintenance
├── SupplyChainProcess
│   ├── ProcurementProcess
│   ├── InventoryManagement
│   ├── InboundLogistics
│   └── OutboundLogistics

# ─── Artifact extensions ────────────────────────────────
OperationalDocument (from Layer 2)
├── BillOfMaterials
├── RoutingSheet
├── QualityReport
│   ├── InspectionReport
│   ├── NonConformanceReport
│   └── CertificateOfConformity
├── MaintenanceWorkOrder
├── ShippingDocument
│   ├── PackingList
│   ├── BillOfLading
│   └── CustomsDeclaration

DataRecord (from Layer 2)
├── ProductionRecord
│   ├── BatchRecord
│   ├── LotRecord
│   └── SerialNumberRecord
├── InventoryRecord
├── QualityMeasurement
```

### Manufacturing-Specific Properties

```yaml
ManufacturedProduct:
  inherits: Product    # gets all Product properties
  additional_properties:
    part_number:      { type: string, required: true }
    revision:         { type: string }
    bill_of_materials:{ type: BillOfMaterials }
    lead_time_days:   { type: integer }
    minimum_order_qty:{ type: integer }
    unit_of_measure:  { type: string }

BillOfMaterials:
  inherits: OperationalDocument
  additional_properties:
    bom_level:        { type: integer }
    parent_product:   { type: ManufacturedProduct }
    components:       { type: BOMLine[] }
    effective_date:   { type: date }
    revision:         { type: string }

BOMLine:
  inherits: DataRecord
  properties:
    component:        { type: Component }
    quantity:         { type: decimal }
    unit_of_measure:  { type: string }
    position:         { type: string }
    is_critical:      { type: boolean }

NonConformanceReport:
  inherits: QualityReport
  additional_properties:
    ncr_number:       { type: string, required: true }
    defect_type:      { type: string }
    severity:         { type: enum[Minor, Major, Critical] }
    root_cause:       { type: string }
    corrective_action:{ type: string }
    disposition:      { type: enum[Rework, Scrap, UseAsIs, ReturnToVendor] }
    affected_batch:   { type: BatchRecord }
```

### 5.3 Example: Financial Services Branch Ontology

```
# ─── Entity extensions (Object branch) ─────────────
# Inheritance chain: Entity → Object → Product
Product (from Layer 2)
├── FinancialProduct
│   ├── LoanProduct
│   ├── InsuranceProduct
│   ├── InvestmentProduct
│   └── PaymentProduct
├── FinancialInstrument
│   ├── Security
│   │   ├── Equity
│   │   ├── Bond
│   │   └── Derivative
│   └── Currency

# ─── Entity extensions (Actor branch) ─────────────────────
# Inheritance chain: Entity → Actor → Organisation → ExternalOrganisation → Client
Client (from Layer 2)
├── RetailClient
├── CorporateClient
├── InstitutionalClient

# ─── Process extensions ─────────────────────────────────
BusinessProcess (from Layer 2)
├── KYCProcess (Know Your Customer)
├── CreditAssessmentProcess
├── ClaimsProcess
├── UnderwritingProcess
├── RegulatoryReportingProcess
├── AMLProcess (Anti-Money Laundering)

# ─── Artifact extensions ────────────────────────────────
FinancialDocument (from Layer 2)
├── LoanAgreement
├── InsurancePolicy
├── ClaimForm
├── RegulatoryFiling
├── RiskAssessmentReport
├── AuditReport

DataRecord (from Layer 2)
├── TransactionRecord
│   ├── PaymentTransaction
│   ├── TradeTransaction
│   └── TransferTransaction
├── AccountRecord
├── PortfolioRecord
├── RiskExposureRecord
```

### 5.4 Example: Professional Services Branch Ontology

```
# ─── Entity extensions (Actor branch) ─────────────────────
# Inheritance chain: Entity → Actor → Organisation → ExternalOrganisation → Client
Client (from Layer 2)
├── EngagementClient

# Inheritance chain: Entity → Actor → Person
Person (from Layer 2)
├── Consultant
├── PrincipalConsultant
├── SubContractor

# ─── Process extensions ─────────────────────────────────
BusinessProcess (from Layer 2)
├── EngagementProcess
│   ├── ProposalProcess
│   ├── ScopingProcess
│   ├── DeliveryProcess
│   └── ClosureProcess
├── ResourcePlanningProcess
├── KnowledgeManagementProcess

Project (from Layer 2)
├── ClientEngagement
│   ├── AdvisoryEngagement
│   ├── ImplementationEngagement
│   └── AuditEngagement

# ─── Artifact extensions ────────────────────────────────
OperationalDocument (from Layer 2)
├── Proposal
├── StatementOfWork
├── ChangeRequest
├── StatusReport
├── Deliverable
├── TimeSheet

FinancialDocument (from Layer 2)
├── FeeNote
├── ExpenseReport
├── ProjectBudget
```

---

## 6. Layer 4 — Organisation Ontology

This is where your organisation's unique vocabulary, processes, and specialisations live. It is the most volatile layer — it changes as your organisation evolves.

### 6.1 What goes in Layer 4?

| Category | Examples |
| --- | --- |
| **Custom process names** | "Stage-Gate Review", "CAB Approval", "Tiger Team Triage" |
| **Organisation-specific document types** | "Blue Form", "Annex 7B", "Customer Specification Sheet" |
| **Internal vocabulary** | "Golden Customer" = Client with revenue > €1M |
| **Custom statuses** | "Parked", "Awaiting Lab Results", "Legal Hold" |
| **Custom roles** | "Site Reliability Lead", "Innovation Champion" |
| **Custom relationships** | "escalatedTo", "co-signedBy", "requires certification from" |
| **System-specific mappings** | tbl_proc_01.fld_x7 → Invoice.totalAmount |

### 6.2 Example: Organisation Extension

```yaml
# Organisation: "AcmeTech Manufacturing BV"
# Branch: Manufacturing
# ─────────────────────────────────────────────

# Custom concept
StageGateReview:
  inherits: ReviewActivity    # from Layer 2
  layer: 4
  additional_properties:
    gate_number:     { type: enum[G0, G1, G2, G3, G4, G5] }
    gate_criteria:   { type: string[] }
    readiness_score: { type: decimal }
    go_no_go:        { type: enum[Go, NoGo, Conditional] }
  synonyms: [gate review, tollgate, phase gate]

# Custom document type
CustomerSpecSheet:
  inherits: Specification    # from Manufacturing Branch (Layer 3)
  layer: 4
  additional_properties:
    customer_part_number:  { type: string }
    customer_revision:     { type: string }
    special_requirements:  { type: string[] }
    approved_by_customer:  { type: boolean }
  synonyms: [spec sheet, customer spec, CSS]

# Custom classification
CustomerTier:
  inherits: Classification    # from Layer 2
  layer: 4
  values:
    - TierA: "Revenue > €1M, strategic"
    - TierB: "Revenue €100K–€1M"
    - TierC: "Revenue < €100K"

# System mapping (connects to metadata extraction)
SystemMapping:
  ERP_System:
    table: tbl_proc_01
    field_mappings:
      fld_x7:  { concept: Invoice, property: total_amount, semantic_label: "Invoice Total (EUR)" }
      fld_x3:  { concept: Invoice, property: invoice_date, semantic_label: "Invoice Date" }
      fld_v1:  { concept: Vendor, property: legal_name, semantic_label: "Vendor Name" }
```

---

## 7. Inheritance Resolution and Extraction Templates

### 7.1 How Extraction Templates Inherit

Each concept carries an extraction template that tells the metadata extraction pipeline what to extract from unstructured sources. Templates inherit and accumulate across layers:

```
LAYER 1: Document
  extraction_template:
    required: [document_date, document_type]
    optional: [summary, author]
                │
                ▼ inherits
LAYER 2: FinancialDocument (extends Document)
  extraction_template:
    inherited_required: [document_date, document_type]      ← from Document
    additional_required: [document_number, amount, currency] ← added
    inherited_optional: [summary, author]                    ← from Document
    additional_optional: [fiscal_year, cost_centre]          ← added
                │
                ▼ inherits
LAYER 2: Invoice (extends FinancialDocument)
  extraction_template:
    inherited_required: [document_date, document_type,       ← from Document
                         document_number, amount, currency]  ← from FinancialDocument
    additional_required: [vendor_name]                       ← added
    inherited_optional: [summary, author,                    ← from Document
                         fiscal_year, cost_centre]           ← from FinancialDocument
    additional_optional: [due_date, tax_amount, line_items,  ← added
                          purchase_order_ref, payment_terms]
                │
                ▼ inherits
LAYER 3: (no manufacturing-specific invoice type)
                │
                ▼ inherits
LAYER 4: AcmeTechInvoice (extends Invoice, org-specific)
  extraction_template:
    inherited_required: [...all from above...]
    additional_required: [acme_project_code]                 ← added
    additional_optional: [acme_cost_bucket, gate_reference]  ← added
    property_refinements:
      currency: { default: "EUR" }                          ← refined
      vendor_name: { resolve_to: Vendor entity registry }   ← refined
```

### 7.2 Resolved Template (what the extraction pipeline actually uses)

When the pipeline needs to extract metadata from a document classified as `AcmeTechInvoice`, it resolves the full template by walking up the inheritance chain:

```yaml
# RESOLVED extraction template for AcmeTechInvoice
# Assembled by merging all layers
concept: AcmeTechInvoice
inherits_from: [Invoice, FinancialDocument, Document]
layer: 4

required_properties:
  # From Layer 1 (Document)
  - document_date:     { type: date }
  - document_type:     { type: string, default: "Invoice" }
  # From Layer 2 (FinancialDocument)
  - document_number:   { type: string }
  - amount:            { type: decimal }
  - currency:          { type: string, default: "EUR" }  # refined in Layer 4
  # From Layer 2 (Invoice)
  - vendor_name:       { type: string, resolve_to: Vendor }  # refined in Layer 4
  # From Layer 4 (AcmeTechInvoice)
  - acme_project_code: { type: string }

optional_properties:
  # From Layer 1 (Document)
  - summary:           { type: string }
  - author:            { type: string }
  # From Layer 2 (FinancialDocument)
  - fiscal_year:       { type: string }
  - cost_centre:       { type: string }
  # From Layer 2 (Invoice)
  - due_date:          { type: date }
  - tax_amount:        { type: decimal }
  - line_items:        { type: array }
  - purchase_order_ref:{ type: string }
  - payment_terms:     { type: string }
  # From Layer 4 (AcmeTechInvoice)
  - acme_cost_bucket:  { type: string }
  - gate_reference:    { type: string }

entity_resolution:
  - vendor_name:   resolve to → Vendor entity registry
  - author:        resolve to → Person entity registry

synonyms: [invoice, bill, factuur, Rechnung, facture, factura,
           acme invoice, project invoice]
```

### 7.3 Query Resolution with Inheritance

When a query asks for a concept, the ontology engine uses the inheritance hierarchy to expand the search:

```
Query: "Find all FinancialDocuments from 2025"

Step 1 — Resolve concept hierarchy:
  FinancialDocument
  ├── Invoice
  │   └── AcmeTechInvoice (Layer 4)
  ├── CreditNote
  ├── Receipt
  ├── Budget
  ├── FinancialReport
  ├── FeeNote (from Professional Services branch, if loaded)
  └── ExpenseReport (from Professional Services branch, if loaded)

Step 2 — Expand query to include all subtypes:
  WHERE primary_concept IN (
    'FinancialDocument', 'Invoice', 'AcmeTechInvoice',
    'CreditNote', 'Receipt', 'Budget', 'FinancialReport',
    'FeeNote', 'ExpenseReport'
  )
  AND properties->>'document_date' >= '2025-01-01'

Step 3 — Run against both structured sources AND metadata store
         (as defined in the v2 architecture)
```

---

## 8. Schema vs Instances — What Lives Where

Before discussing serialisation, a crucial distinction must be made. The ontology manages two fundamentally different kinds of data, and conflating them leads to poor architecture decisions.

### 8.1 The Ontology Schema (concept definitions — small, stable)

The **schema** defines the concepts, properties, relationships, mixins, extraction templates, and inheritance rules. This is what the YAML files contain. It answers: "What kinds of things exist, and how are they structured?"

For a realistic enterprise ontology, the schema consists of roughly 200–300 concepts across all four layers, each with 3–10 properties and 1–5 relationships. That amounts to approximately 8,000–15,000 lines of YAML, or 300–500KB. This is trivially small — it fits in memory on any device.

The schema changes infrequently and through governed processes: PR reviews, Ontology Owner approvals, version bumps. It is a definitional asset, not a data store.

### 8.2 The Ontology Instances (extracted metadata, records — large, growing)

**Instances** are the actual data classified against the schema: the 47,000 invoices, 12,000 employees, 3 million metadata records extracted from documents. These are the individual things that belong to each concept. Instances answer: "What specific invoices do we have, and what do they contain?"

Instances **never live in YAML**. They live in:

- The metadata store (extracted from unstructured sources, as defined in the v2 architecture)
- Operational databases (ERP, CRM, HRIS, etc.)
- The mapping registry (which bridges database fields to ontology concepts)

This separation is non-negotiable. The YAML files define the shape of the world; databases hold the world itself.

```
┌──────────────────────────────────┐    ┌──────────────────────────────────┐
│  ONTOLOGY SCHEMA (YAML files)    │    │  ONTOLOGY INSTANCES (databases)  │
│                                  │    │                                  │
│  "An Invoice has a vendor,       │    │  Invoice #INV-2025-0042          │
│   an amount, a due_date,         │    │    vendor: "Bosch GmbH"          │
│   and is a FinancialDocument"    │    │    amount: €14,520.00            │
│                                  │    │    due_date: 2025-03-15          │
│  ~300 concepts, ~500KB           │    │    ... (one of 47,000)           │
│  Changes: monthly                │    │                                  │
│  Storage: Git                    │    │  ~millions of records            │
│                                  │    │  Changes: continuously           │
│                                  │    │  Storage: PostgreSQL / metadata  │
│                                  │    │           store                  │
└──────────────────────────────────┘    └──────────────────────────────────┘
```

### 8.3 YAML as the Source of Truth for the Schema

YAML is the authoring format for the ontology schema. It is chosen because:

- **Human-readable**: a domain steward can review a concept definition without tooling.
- **Diffable**: Git shows exactly what changed between versions.
- **Commentable**: explanations and rationale live alongside definitions.
- **Reviewable**: PRs for ontology changes are as natural as code reviews.

```yaml
# ─── Ontology metadata ────────────────────────
ontology:
  name: "AcmeTech Ontology"
  version: "1.2.0"
  layers:
    - { id: L1, name: "Foundation",  source: "foundation.yaml",  locked: true }
    - { id: L2, name: "Enterprise",  source: "enterprise.yaml",  locked: true }
    - { id: L3, name: "Manufacturing", source: "manufacturing.yaml", locked: false }
    - { id: L4, name: "AcmeTech",   source: "acmetech.yaml",    locked: false }

# ─── Concept definition format ─────────────────
concepts:

  - id: "Invoice"
    layer: L2
    inherits: "FinancialDocument"
    abstract: false
    label: "Invoice"
    description: "A demand for payment for goods or services delivered"
    synonyms: ["bill", "factuur", "Rechnung", "facture"]
    mixins: []   # already inherited from FinancialDocument
    properties:
      - { name: "invoice_type", type: "enum", values: ["Standard", "Proforma", "Recurring"], required: false }
      - { name: "due_date", type: "date", required: false }
      - { name: "payment_terms", type: "string", required: false }
      - { name: "vendor", type: "ref:Vendor", required: true }
      - { name: "tax_amount", type: "decimal", required: false }
      - { name: "purchase_order_ref", type: "ref:PurchaseOrder", required: false }
    relationships:
      - { name: "paidVia", target: "TransactionRecord", cardinality: "0..*" }
      - { name: "fulfilledBy", target: "PurchaseOrder", cardinality: "0..1" }
    extraction_template:
      classification_hints: ["invoice", "inv-", "factuur", "rechnung"]
      file_patterns: ["**/invoices/**", "**/facturen/**"]
```

However, YAML has limitations as a runtime format. YAML parsing is slow (~1–2MB/s in Python), there is no query capability, and loading + resolving inheritance on every API request would be wasteful. This is why we compile.

### 8.4 The Hybrid Approach: YAML Authored, SQLite Compiled

The schema follows a **compile-on-deploy** model, similar to how code is authored in a high-level language but compiled for execution:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AUTHORING TIME                              │
│                                                                     │
│  YAML files in Git          Human editing, PRs, reviews             │
│  (source of truth)          Domain stewards work here               │
│                                                                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼  ontology compile (CI/CD build step)
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    │   1. Parse all YAML     │
                    │   2. Resolve inheritance│
                    │   3. Merge templates    │
                    │   4. Build indexes      │
                    │   5. Validate rules     │
                    │   6. Write to SQLite    │
                    │                         │
                    └────────────┬────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          RUNTIME                                    │
│                                                                     │
│  ontology.db (SQLite)       Pre-resolved, indexed, queryable        │
│  (compiled artifact)        Application services read from here     │
│                                                                     │
│  Used by:                                                           │
│  • Semantic Query Engine    (concept lookup, hierarchy traversal)    │
│  • Extraction Pipeline      (template resolution, classification)   │
│  • Mapping Registry         (DB field → concept.property)           │
│  • LLM Context Assembly     (concept definitions for AI prompts)    │
│  • Ontology Manager UI      (browsing, searching, visualisation)    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Why SQLite as the compiled format?**

- **Zero infrastructure**: ships as a single file, no database server required.
- **Embedded**: the application opens the file directly, no network round-trips.
- **Queryable**: SQL for concept lookups, hierarchy traversal, synonym search.
- **Indexed**: B-tree indexes on concept IDs, synonyms, layers — sub-millisecond lookups.
- **Portable**: the same `.db` file works on any platform, any language.
- **Atomic deployment**: swap one file to deploy a new ontology version.
- **Read-optimised**: the ontology schema is read-heavy, write-never at runtime (writes go back to YAML via the governance process).

For organisations that already run PostgreSQL, the same compiled schema can be loaded into a `pg_ontology` schema instead of SQLite. The table design is identical.

### 8.5 Ontology File Structure

```
ontology/
├── ontology.yaml                  # Master manifest, references all layers
├── foundation/                    # Layer 1 (locked, versioned)
│   ├── foundation.yaml            #   Core concepts and relationships
│   └── mixins.yaml                #   Cross-cutting property sets
├── enterprise/                    # Layer 2 (locked, versioned)
│   ├── entities.yaml              #   Actor + Object specialisations
│   ├── processes.yaml             #   Process, Task, Event specialisations
│   ├── artifacts.yaml             #   Document, DataRecord specialisations
│   └── domain-knowledge.yaml      #   Classifications, Business Domains
├── branches/                      # Layer 3 (pick one or more)
│   ├── manufacturing/
│   │   ├── manufacturing.yaml
│   │   └── extraction-templates/
│   │       ├── bom.yaml
│   │       ├── ncr.yaml
│   │       └── ...
│   ├── financial-services/
│   │   └── financial-services.yaml
│   ├── professional-services/
│   │   └── professional-services.yaml
│   ├── healthcare/
│   │   └── healthcare.yaml
│   ├── retail/
│   │   └── retail.yaml
│   └── public-sector/
│       └── public-sector.yaml
├── organisation/                  # Layer 4 (your extensions)
│   ├── acmetech.yaml
│   ├── system-mappings/
│   │   ├── erp-mappings.yaml
│   │   ├── crm-mappings.yaml
│   │   └── sharepoint-mappings.yaml
│   └── extraction-templates/
│       ├── acme-invoice.yaml
│       └── stage-gate-review.yaml
├── build/                         # Compilation output (gitignored)
│   └── ontology.db                #   Compiled SQLite database
└── scripts/
    ├── compile.py                 #   YAML → SQLite compiler
    └── validate.py                #   Pre-commit validation checks
```

### 8.6 The Compiled SQLite Schema

The `compile.py` script reads all YAML files, resolves inheritance, merges templates, runs validation, and writes the resolved ontology to a SQLite database with the following schema:

```sql
-- ═══════════════════════════════════════════════════════════════════
-- COMPILED ONTOLOGY SCHEMA (SQLite)
-- ═══════════════════════════════════════════════════════════════════
-- This database is generated by compile.py from the YAML source files.
-- It is a READ-ONLY runtime artifact. All edits go through YAML + Git.
-- ═══════════════════════════════════════════════════════════════════

-- ─── Metadata ────────────────────────────────────────────────────

CREATE TABLE ontology_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
-- Stores: name, version, compiled_at, source_commit, layer_versions

-- ─── Layers ──────────────────────────────────────────────────────

CREATE TABLE layers (
    id          TEXT PRIMARY KEY,       -- 'L1', 'L2', 'L3', 'L4'
    name        TEXT NOT NULL,          -- 'Foundation', 'Enterprise', ...
    version     TEXT NOT NULL,          -- semver
    locked      BOOLEAN NOT NULL,
    description TEXT
);

-- ─── Concepts ────────────────────────────────────────────────────
-- One row per concept. The inheritance chain is pre-resolved at
-- compile time and stored as a JSON array for fast traversal.

CREATE TABLE concepts (
    id              TEXT PRIMARY KEY,       -- 'Invoice'
    layer_id        TEXT NOT NULL REFERENCES layers(id),
    inherits        TEXT REFERENCES concepts(id),
    abstract        BOOLEAN NOT NULL DEFAULT 0,
    label           TEXT NOT NULL,
    description     TEXT,
    bfo_equivalent  TEXT,                   -- NULL if no BFO mapping

    -- Pre-resolved at compile time (avoids runtime tree-walking)
    inheritance_chain   TEXT NOT NULL,      -- JSON: ["Thing","Entity","Resource","Document","FinancialDocument","Invoice"]
    depth               INTEGER NOT NULL,   -- Distance from Thing (0 = Thing itself)
    all_descendants     TEXT NOT NULL        -- JSON: ["PurchaseInvoice","CreditNote","AcmeTechInvoice",...]
);

CREATE INDEX idx_concepts_layer ON concepts(layer_id);
CREATE INDEX idx_concepts_inherits ON concepts(inherits);
CREATE INDEX idx_concepts_depth ON concepts(depth);

-- ─── Synonyms ────────────────────────────────────────────────────
-- Denormalised lookup table. Includes synonyms from all ancestors
-- (accumulated through inheritance). Enables fast synonym → concept
-- resolution for classification and search.

CREATE TABLE synonyms (
    synonym         TEXT NOT NULL,          -- 'factuur', 'bill', 'Rechnung'
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    defined_in      TEXT NOT NULL REFERENCES concepts(id), -- Where synonym was declared
    language        TEXT,                   -- ISO 639-1, NULL if unspecified
    PRIMARY KEY (synonym, concept_id)
);

CREATE INDEX idx_synonyms_lookup ON synonyms(synonym COLLATE NOCASE);

-- ─── Properties ──────────────────────────────────────────────────
-- Fully resolved: each concept has ALL its properties listed here,
-- including those inherited from ancestors and injected by mixins.
-- The 'source' column tells you where each property was defined.

CREATE TABLE properties (
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,          -- 'string', 'date', 'decimal', 'ref:Vendor', 'enum', ...
    required        BOOLEAN NOT NULL DEFAULT 0,
    description     TEXT,
    default_value   TEXT,                   -- JSON-encoded default, NULL if none
    enum_values     TEXT,                   -- JSON array for enum types, NULL otherwise
    source          TEXT NOT NULL,          -- 'own', 'inherited', 'mixin'
    defined_in      TEXT NOT NULL,          -- Concept or mixin ID where this was first defined
    defined_in_layer TEXT NOT NULL REFERENCES layers(id),
    PRIMARY KEY (concept_id, name)
);

CREATE INDEX idx_properties_concept ON properties(concept_id);
CREATE INDEX idx_properties_source ON properties(source);

-- ─── Relationships ───────────────────────────────────────────────
-- Fully resolved: includes inherited relationships from ancestors.

CREATE TABLE relationships (
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    name            TEXT NOT NULL,          -- 'paidVia', 'issuedBy', 'hasInput'
    target          TEXT NOT NULL REFERENCES concepts(id),
    cardinality     TEXT NOT NULL,          -- '0..1', '1..1', '0..*', '1..*'
    inverse         TEXT,                   -- Name of the inverse relationship, if declared
    description     TEXT,
    defined_in      TEXT NOT NULL,          -- Concept ID where this was first defined
    defined_in_layer TEXT NOT NULL REFERENCES layers(id),
    PRIMARY KEY (concept_id, name)
);

CREATE INDEX idx_relationships_concept ON relationships(concept_id);
CREATE INDEX idx_relationships_target ON relationships(target);

-- ─── Mixins ──────────────────────────────────────────────────────

CREATE TABLE mixins (
    id              TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE mixin_properties (
    mixin_id        TEXT NOT NULL REFERENCES mixins(id),
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    required        BOOLEAN NOT NULL DEFAULT 0,
    description     TEXT,
    default_value   TEXT,
    enum_values     TEXT,
    PRIMARY KEY (mixin_id, name)
);

-- Which concepts have which mixins (resolved through inheritance)
CREATE TABLE concept_mixins (
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    mixin_id        TEXT NOT NULL REFERENCES mixins(id),
    source          TEXT NOT NULL,          -- 'own' or 'inherited'
    defined_in      TEXT NOT NULL,          -- Concept that originally declared this mixin
    PRIMARY KEY (concept_id, mixin_id)
);

-- ─── Extraction Templates ────────────────────────────────────────
-- Fully resolved: merged classification hints and file patterns
-- from all ancestors. Ready for direct use by the extraction pipeline.

CREATE TABLE extraction_templates (
    concept_id              TEXT PRIMARY KEY REFERENCES concepts(id),
    classification_hints    TEXT NOT NULL,   -- JSON array (merged from all ancestors)
    file_patterns           TEXT NOT NULL,   -- JSON array (merged from all ancestors)
    contributing_concepts   TEXT NOT NULL    -- JSON array of concept IDs that contributed
);

CREATE INDEX idx_extraction_hints ON extraction_templates(classification_hints);

-- ─── System Mappings ─────────────────────────────────────────────
-- Bridges between source system fields and ontology concept properties.
-- Used by the Mapping Registry to translate structured data queries.

CREATE TABLE system_mappings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system   TEXT NOT NULL,          -- 'SAP ERP', 'Salesforce', ...
    source_table    TEXT NOT NULL,          -- 'tbl_proc_01', 'Account', ...
    source_field    TEXT NOT NULL,          -- 'fld_x7', 'Name', ...
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    property_name   TEXT NOT NULL,
    semantic_label  TEXT,                   -- Human-readable: "Invoice Total (EUR)"
    transform       TEXT,                   -- Optional transformation rule
    UNIQUE (source_system, source_table, source_field)
);

CREATE INDEX idx_mappings_concept ON system_mappings(concept_id);
CREATE INDEX idx_mappings_source ON system_mappings(source_system, source_table);
```

### 8.7 What the Compiler Resolves

The compile step does significant work so that no runtime service needs to walk inheritance trees:

| What | YAML (source) | SQLite (compiled) |
| --- | --- | --- |
| **Inheritance chain** | Implicit (`inherits: "FinancialDocument"`) | Pre-computed JSON array: `["Thing","Entity","Resource","Document","FinancialDocument","Invoice"]` |
| **All descendants** | Not present | Pre-computed JSON array per concept (enables substitution queries) |
| **Properties** | Only own properties listed per concept | Fully resolved: own + inherited + mixin properties, each tagged with source |
| **Synonyms** | Only own synonyms per concept | Accumulated: own + all ancestor synonyms, each tagged with origin |
| **Extraction templates** | Only own hints and patterns | Merged: hints and patterns from entire inheritance chain |
| **Relationships** | Only own relationships | Fully resolved: own + inherited, each tagged with origin |
| **Mixins** | Declared on the concept | Resolved: own + inherited from ancestors |
| **Validation** | Not checked | All rules enforced; invalid schema fails to compile |

### 8.8 Typical Compiled Database Size

For a realistic enterprise ontology:

| Metric | Approximate |
| --- | --- |
| Concepts | 200–300 |
| Properties (resolved) | 2,000–4,000 rows |
| Synonyms (resolved) | 1,500–3,000 rows |
| Relationships (resolved) | 500–1,000 rows |
| Extraction templates | 80–150 rows |
| System mappings | 100–500 rows |
| **SQLite file size** | **500KB–2MB** |
| **Load time** | **< 50ms** |

This is a file you can email. It loads in under 50 milliseconds and every query returns in under 1 millisecond. No server infrastructure required.

### 8.9 Version Control and Governance

```
Git branching model:

main ─────────────────────────────────────────────▶
  │
  ├── Layer 1 & 2 changes require PR + Ontology Owner approval
  │
  ├── Layer 3 changes require PR + Domain Steward approval
  │
  └── Layer 4 changes require PR + Data Steward approval

Each layer has its own semver:
  foundation:            v1.0.0  (stable, rarely changes)
  enterprise:            v2.3.0  (evolves with new universal concepts)
  manufacturing-branch:  v1.1.0  (evolves with industry standards)
  acmetech:              v3.7.2  (evolves with org changes)

CI/CD pipeline:
  1. PR opened → validate.py runs (syntax, references, rule checks)
  2. PR merged → compile.py runs (YAML → ontology.db)
  3. ontology.db deployed to application services
  4. Services reload the compiled database (hot-swap, zero downtime)
```

---

## 9. Runtime Architecture: How the Compiled Ontology Is Used

At runtime, no service reads YAML files. Every service reads from the compiled `ontology.db` (SQLite) or its PostgreSQL equivalent. The compile step has already resolved all inheritance, merged all templates, and built all indexes.

### 9.1 Runtime Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPILED ONTOLOGY (ontology.db)                   │
│                                                                     │
│  Pre-resolved, indexed, queryable. ~1MB. Loads in <50ms.           │
│  Read-only at runtime. Rebuilt on every schema change via CI/CD.    │
│                                                                     │
└─────────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
          │          │          │          │          │
          ▼          ▼          ▼          ▼          ▼
  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ ┌─────────────┐
  │ Semantic   │ │ Metadata │ │ Mapping  │ │  LLM  │ │  Ontology   │
  │ Query      │ │ Extract. │ │ Registry │ │Context│ │  Manager UI │
  │ Engine     │ │ Pipeline │ │          │ │  Assy │ │             │
  └────────────┘ └──────────┘ └──────────┘ └───────┘ └─────────────┘
```

### 9.2 How Each Service Uses the Compiled Ontology

**Semantic Query Engine** — receives natural-language or structured queries, resolves them against the ontology:

```sql
-- "Find all FinancialDocuments from 2025"
-- Step 1: Look up descendants (pre-computed, no tree-walking)
SELECT all_descendants FROM concepts WHERE id = 'FinancialDocument';
-- Returns: ["Invoice","CreditNote","Receipt","Budget","FinancialReport",
--           "AcmeTechInvoice","FeeNote","ExpenseReport"]

-- Step 2: Query the metadata store / databases using the expanded list
SELECT * FROM metadata_records
WHERE primary_concept IN ('FinancialDocument','Invoice','CreditNote',...)
  AND properties->>'document_date' >= '2025-01-01';
```

**Metadata Extraction Pipeline** — classifies incoming documents and extracts properties:

```sql
-- Step 1: Classify using synonyms and hints
SELECT c.id, c.label, c.inheritance_chain
FROM synonyms s JOIN concepts c ON s.concept_id = c.id
WHERE s.synonym = 'factuur';
-- Returns: Invoice, with chain ["Thing","Entity","Resource","Document",
--          "FinancialDocument","Invoice"]

-- Step 2: Load the fully resolved extraction template
SELECT classification_hints, file_patterns
FROM extraction_templates WHERE concept_id = 'Invoice';
-- Returns merged hints/patterns from Document + FinancialDocument + Invoice

-- Step 3: Load all resolved properties for extraction
SELECT name, type, required, description
FROM properties WHERE concept_id = 'Invoice';
-- Returns 15+ properties: own + inherited + mixin, ready to extract
```

**Mapping Registry** — translates structured database queries:

```sql
-- "What ontology property does ERP field tbl_proc_01.fld_x7 map to?"
SELECT concept_id, property_name, semantic_label
FROM system_mappings
WHERE source_system = 'SAP ERP'
  AND source_table = 'tbl_proc_01'
  AND source_field = 'fld_x7';
-- Returns: concept=Invoice, property=total_amount, label="Invoice Total (EUR)"
```

**LLM Context Assembly** — builds ontology-aware context for AI requests:

```sql
-- Load everything the LLM needs to understand a concept
SELECT c.label, c.description, c.inheritance_chain,
       p.name, p.type, p.required, p.description
FROM concepts c
JOIN properties p ON p.concept_id = c.id
WHERE c.id = 'Invoice';
-- Assembled into a structured prompt section for the LLM
```

### 9.3 Conflict Resolution Rules

These rules are enforced at compile time. If any rule is violated, `compile.py` exits with an error and no `ontology.db` is produced.

| Conflict Type | Resolution |
| --- | --- |
| Same concept name in two layers | Lower layer wins (more specific). Must explicitly declare `extends`. |
| Property type mismatch (parent: string, child: integer) | **Compile error.** Child must be compatible with parent type. |
| Required in parent, optional in child | **Compile error.** Child cannot weaken constraints. |
| Optional in parent, required in child | Allowed. Child can strengthen constraints (narrowing). |
| New property in child with same name as parent | **Compile error.** Must use a distinct name or explicitly override. |
| Synonym collision (same synonym maps to two concepts) | **Compile warning.** Disambiguation rules applied (prefer more specific concept). |
| Broken reference (inherits or ref: target does not exist) | **Compile error.** All references must resolve. |
| Circular inheritance | **Compile error.** Detected via topological sort. |

### 9.4 Hot-Reloading the Ontology

When a new version of the ontology is compiled and deployed:

1. CI/CD produces a new `ontology.db` file.
2. The file is placed in a known location (or pushed to a shared store / S3 bucket).
3. Each service detects the new file (via filesystem watch, polling, or deployment signal).
4. The service opens the new database, validates the version, and atomically swaps its internal reference.
5. In-flight requests complete against the old version; new requests use the new version.
6. The old database file is released after all in-flight requests finish.

For SQLite, this is trivial — opening a second read-only connection to a new file and swapping references is an atomic operation. No downtime, no restarts.

---

## 10. Connecting to the Metadata Extraction Architecture (v2)

This layered ontology feeds directly into the metadata extraction design from the v2 document:

```
Unstructured document arrives
        │
        ▼
STEP 1: CLASSIFY (using resolved ontology)
        │  "What concept is this?"
        │  Uses: classification_hints, file_patterns, synonyms
        │  from ALL layers (accumulated through inheritance)
        │
        │  Result: "This is an Invoice" (confidence: 0.92)
        │  Or more specific: "This is an AcmeTechInvoice" (0.88)
        │
        ▼
STEP 2: LOAD RESOLVED EXTRACTION TEMPLATE
        │  Walk up inheritance chain:
        │  AcmeTechInvoice → Invoice → FinancialDocument → Document
        │  Merge all required + optional properties
        │
        ▼
STEP 3: EXTRACT PROPERTIES (using merged template)
        │  Extract each property defined in the resolved template
        │  Properties from Layer 1 + 2 + 3 + 4 all extracted together
        │
        ▼
STEP 4: STORE METADATA RECORD
        │  primary_concept: "AcmeTechInvoice"
        │  concept_hierarchy: ["Document", "FinancialDocument",
        │                      "Invoice", "AcmeTechInvoice"]
        │  properties: { ...all extracted values... }
        │
        ▼
QUERYABLE: Any query for "Document", "FinancialDocument",
           "Invoice", or "AcmeTechInvoice" will find this record
           (substitution principle in action)
```

The `concept_hierarchy` field stored in each metadata record is what enables the substitution principle at query time. A query for `FinancialDocument` matches any record whose `concept_hierarchy` includes `FinancialDocument`.

---

## 11. Implementation Roadmap for the Foundation

### Phase 1: Define and Validate (Weeks 1–4)

```
Week 1–2: Foundation + Enterprise layers
├── Draft Layer 1 (foundational taxonomy) in YAML          ✓ done
├── Draft Layer 2 (universal enterprise concepts) in YAML
├── Define mixins                                          ✓ done
├── Define universal relationships
├── Review with 3–5 domain experts from different departments
└── Validate: "Can we describe 80% of common requests with these concepts?"

Week 3–4: Branch + Organisation layers
├── Select and draft relevant Branch ontology (Layer 3)
├── Draft initial Organisation extensions (Layer 4)
├── Map 10–20 most-queried database fields to ontology concepts
├── Define extraction templates for top 5 document types
└── Validate: "Can we resolve 10 real historical requests against this ontology?"
```

### Phase 2: Build Tooling (Weeks 3–8)

```
├── Build validate.py (pre-commit: syntax, references, rule checks)
├── Build compile.py  (YAML → SQLite compiler)
│   ├── YAML loader (reads ontology.yaml manifest, loads all layers in order)
│   ├── Inheritance resolver (walks parent chains, detects cycles)
│   ├── Property resolver (merges own + inherited + mixin properties)
│   ├── Synonym accumulator (collects synonyms up the chain)
│   ├── Extraction template merger (merges hints and patterns)
│   ├── Descendant indexer (pre-computes all_descendants per concept)
│   ├── Validation engine (enforces all conflict resolution rules)
│   └── SQLite writer (creates ontology.db with indexes)
├── Set up CI/CD pipeline (PR validation → compile → deploy)
├── Build Ontology Query API (thin REST/GraphQL over SQLite)
└── Integrate with metadata extraction pipeline (from v2 design)
```

### Phase 3: Populate and Test (Weeks 6–12)

```
├── Map structured data sources via Layer 4 system mappings
├── Run extraction pipeline on first batch of documents
├── Test query resolution with real requests via compiled ontology
├── Measure: coverage, precision, extraction accuracy
├── Iterate: add missing concepts, fix misclassifications
│   (edit YAML → PR → compile → deploy → re-test)
└── Document lessons learned, update extraction templates
```

---

## 12. Key Design Principles (Revised)

1. **Inherit, don't duplicate.** If a property applies to all `FinancialDocuments`, define it once on `FinancialDocument`. Never repeat it on `Invoice`, `CreditNote`, `Receipt`.
2. **Specialise downward, query upward.** Define concepts at the most specific level needed. Query at whatever level of generality the user requires. The substitution principle handles the rest.
3. **Layers are additive, never contradictory.** A lower layer can add concepts and strengthen constraints. It cannot remove properties or weaken constraints defined in a higher layer.
4. **Start with Layer 2.** The Universal Enterprise Ontology is where 80% of value comes from. Get this right first, then add branch and organisation layers.
5. **Branch ontologies are optional.** Not every organisation needs one. If your concepts are adequately covered by Layer 2, skip straight to Layer 4.
6. **Keep Layer 1 tiny and stable.** The foundational layer should have fewer than 30 concepts. It provides the structural grammar, not the business vocabulary.
7. **YAML authored, SQLite compiled.** YAML is the source of truth for humans; SQLite is the runtime format for machines. The compile step resolves inheritance, merges templates, and builds indexes so that no runtime service needs to walk trees or parse YAML. Edit in YAML, deploy as SQLite.
8. **Extraction templates are first-class citizens.** Every concrete (non-abstract) concept should have an extraction template. Without it, the concept cannot be used for metadata extraction from unstructured sources.
9. **Synonyms are not optional.** People say "bill", "invoice", "factuur", "Rechnung". If your ontology only understands "invoice", it fails on 75% of real-world queries.
10. **Version everything.** Each layer has its own version. Changes to locked layers (1, 2) require formal review. Changes to unlocked layers (3, 4) follow lighter governance.