# Implementatieplan en User Stories: Kennisbank Evolutie

> **Doelgroep**: Ontwikkelaars, Architecten en Product Owners
> **Doel**: Een gedetailleerd stappenplan en user stories bieden voor de overgang naar een geavanceerde, hybride (Graph + Vector) RAG kennisbank, gebaseerd op de eerder voorgestelde fasering (Fase 1 t/m 3).

## Theoretische Achtergrond bij Implementatie
Bij het bouwen van een robuuste AI-gedreven kennisbank is iteratief werken cruciaal. We splitsen het proces op in drie pijlers:
1. **Verrijken van Opslag (Fase 1)**: De overstap van een platte (key-value) datastructuur naar een relationele (graaf) structuur voor document-metadata.
2. **Semantische Zoekmogelijkheden (Fase 2)**: Het toevoegen van vector-gebaseerde zoektechnieken (via embeddings en pgvector) om betekenis in plaats van alleen exacte trefwoorden te vinden.
3. **Hybride Retrieval & Generatie (Fase 3)**: Het samenvoegen van graaf- en vector-zoekopdrachten (Retrieval-Augmented Generation) om natuurlijke taalvragen accuraat te beantwoorden en hallucinaties te minimaliseren door feitelijke gronding (citations).

Hieronder volgt het plan vertaald naar epics en user stories, gedetailleerd opgesteld voor het ontwikkelteam.

---

## Epic 1: Relationele Extractie & Entiteit Resolutie (Fase 1)
*Doel: Verschuiven van puur property-based extractie naar het vastleggen van relaties tussen concepten.*

### User Stories

**US 1.1: LLM Tool-Calling Uitbreiding voor Relaties**
* **Als** AI Developer
* **Wil ik** de `submit_document` LLM tool uitbreiden met een optionele `extracted_relationships` eigenschap in plaats van alleen onafhankelijke properties
* **Zodat** de LLM tijdens het parsen expliciet de verbindingen tussen entiteiten (bijv. "Persoon X is Manager van Afdeling Y") of naar externe stamdata direct als structuur aan ons teruggeeft.
* **Acceptatiecriteria/Voorbeelden**:
  * De tool schema's in `LLMClient` (zoals in `05-llm-integratie.md`) worden bijgewerkt.
  * De payload specificeert het gewenste formaat, bv: `[{"source_concept": "Invoice", "relation": "uitgegeven_door", "target_entity_name": "Bedrijf X"}]`

**US 1.2: Relatie Opslag in de Database**
* **Als** Backend Developer
* **Wil ik** het inkomende relatiedata-formaat correct vertalen en wegschrijven naar de PostgreSQL database 
* **Zodat** deze dwarsverbanden onafhankelijk van het oorspronkelijke document als een "Graph Edge" kunnen worden bevraagd.
* **Acceptatiecriteria/Voorbeelden**:
  * Modelleren van een nieuwe `ConceptRelationshipEntity` of het uitbreiden van het JSONB database-schema zodat edges via SQL (of GIN indexen) navigeerbaar zijn.
  * De `MetadataExtractionService` persist de edges.

**US 1.3: Entity Resolution (Ontdubbelen)**
* **Als** Data Steward / Systeem
* **Wil ik** dat nieuw geëxtraheerde entiteiten met sterk vergelijkbare namen (zoals "Google", "Google LLC" en "Google Inc.") worden samengevoegd onder één unieke Database ID in de Kennisbank
* **Zodat** de opgebouwde relatiegrafiek niet vervuild raakt met losse knooppunten die in realiteit hetzelfde object voorstellen.
* **Acceptatiecriteria/Voorbeelden**:
  * Een `EntityResolutionService` is beschikbaar, op te roepen vóórdat een target entiteit fysiek wordt toegevoegd. Deze maakt gebruik van simpele string similarity of een embedding matching om te controleren of er al een matchend concept is in the Knowledge Base.

---

## Epic 2: Vector Zoeken en Document Embeddings (Fase 2)
*Doel: Implementatie van theorie-gedreven infrastructuur voor semantisch zoeken via embeddings en `pgvector`.*

### User Stories

**US 2.1: Configuratie van pgvector in PostgreSQL**
* **Als** Database Administrator / Backend Developer
* **Wil ik** de `pgvector` extensie configureren op de bestaande PostgreSQL database en een bijbehorende kolom aan de documentlaag toevoegen
* **Zodat** vector embeddings (de semantische numerieke afdruk van een tekst) dichtbij de bestaande metadata bewaard worden, en via cosinus-similariteit of HNSW razendsnel op te zoeken zijn.
* **Acceptatiecriteria/Voorbeelden**:
  * Alembic migratiescript dat `CREATE EXTENSION IF NOT EXISTS vector;` uitvoert.
  * Een SQLAlchemy modelwijziging: `embedding = Column(Vector(1536))` afhankelijk van het embed model.

**US 2.2: Document Chunking Strategie & Pijplijn**
* **Als** Data Pipeline Developer
* **Wil ik** dat lange of complexe teksten systematisch worden opgedeeld in semantisch logische "chunks" (blokken) — bijvoorbeeld per alinea of sectie, met enige tekst-overlap
* **Zodat** het LLM straks specifieke focus heeft en zoekresultaten zich beperken tot het meest relevante fragment in plaats van een 50-pagina document in te zenden.
* **Acceptatiecriteria/Voorbeelden**:
  * Gebruik van bibliotheken als LangChain's `RecursiveCharacterTextSplitter` om bestanden via de bestaande Document Upload op te knippen en tijdelijk (in geheugen of job queue) op te slaan voor embedding generatie.

**US 2.3: Genereren en Opslaan van Embeddings**
* **Als** AI Developer
* **Wil ik** een generieke `generate_embeddings` methode aan de iterface `LLMClient` toevoegen, verbonden met onze LLM provider (bijv. via text-embedding-ada-002, voyage, of nomic)
* **Zodat** alle tekst-chunks volautomatisch asynchroon omgezet worden in vectoren na upload of bewerking, zonder dat een gebruiker daar op moet wachten.
* **Acceptatiecriteria/Voorbeelden**:
  * Toepassing van dependency injection in clean architecture.
  * Bulk-operaties om API-rate-limits te respecteren (batch-size van bv. 50 chunks tegelijk in één LLM verzoek).

---

## Epic 3: Hybride RAG en Vraagbeantwoording (Fase 3)
*Doel: Ontwikkeling van de gebruikerservaring, de query pijplijn en feitelijk correcte generatie (de UI + applicatie integratie).*

### User Stories

**US 3.1: Vraag-Analyse (Intelligent Routing / Question Understanding)**
* **Als** Backend RAG Service
* **Wil ik** een inkomende, natuurlijke (ongeordende) gebruikersvraag door een klein, snel LLM laten analyseren om relevante categorieën, ontologische concepten en tijdspanne-filters af te leiden
* **Zodat** zoekopdrachten kunnen worden geoptimaliseerd en we niet lukraak in miljoenen vectoren (zonder filtering) gaan zoeken.
* **Acceptatiecriteria/Voorbeelden**:
  * Voor een vraag: "Wat is het huidige budget voor IT leveranciers?" retourneert de parser (JSON): `{"conceptFilters": ["Contract", "Finance"], "keywords": "IT budget leverancier"}`.

**US 3.2: Hybride Retrieval Pijplijn (Graph + Vector mix)**
* **Als** RAG Service
* **Wil ik** een zoekopdracht uitvoeren in PostgreSQL die filtert op de concept-eigenschappen (Graph Retrieval, US3.1) EN ordent op semantische gelijkenis met de vraag via de vector index (Vector Retrieval, US2.1)
* **Zodat** we exact de juiste document-chunks kunnen isoleren en samenstellen tot een uiterst pertinente "Golden Context" string.
* **Acceptatiecriteria/Voorbeelden**:
  * De resulterende data is een geplakt stuk tekst, inclusief `[Doc ID: xyz]` labels, klaar voor injectie in de eind-prompt voor de LLM.

**US 3.3: Genereer Antwoord met Klikbare Bronverwijzingen (Citations)**
* **Als** Kennisbank Eenheidgebruiker
* **Wil ik** dat het gegenereerde tekstuele antwoord transparante referentienummers (citations) bevat (bijv. "[1]", "[2]") die navigeren naar de specifieke documenten die voor de bewering(en) zijn gebruikt
* **Zodat** ik altijd the waarheid en context van het brondocument of beleid kan herleiden.
* **Acceptatiecriteria/Voorbeelden**:
  * De pre-fill prompt vereist: "Je moet alle feiten funderen door er altijd een `[doc_id]` aan te koppelen".
  * In React is de markdown-rendering engine (bijvoorbeeld zoals de bestaande in Foundry) uitgebreid zodat de output-tags klikbare links/popovers naar de `ResourcesPage` worden, exact openend bij het ge-highlighte stuk tekst.
