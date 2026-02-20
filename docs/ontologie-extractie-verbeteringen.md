# Visie en Verbeterplan: Ontologie-gestuurde Informatie Extractie en RAG

> **Doelgroep**: Ontwikkelaars en Architecten
> **Doel**: Een groeistrategie definiëren om vanuit de huidige applicatie te evolueren naar een enterprise-brede, doorzoekbare kennisbank die zowel gestructureerde als ongestructureerde data contextueel begrijpt.

## 1. Inleiding

Het doel is om een kennisbank op te zetten die als "Single Source of Truth" dient voor organisatiebrede vragen. Deze kennisbank moet in staat zijn om de **juiste context** te verzamelen door zowel *gestructureerde* data (zoals factuurbedragen of datums) als *ongestructureerde* data (zoals rapportages, beleidsstukken, of notulen) te verenigen onder een **gedeelde ontologie**.

Dit document analyseert de huidige architectuur, belicht relevante industriële best practices (zoals Ontology-Based Information Extraction en Knowledge Graphs) en presenteert een gefaseerde roadmap met verbeterpunten.

---

## 2. Huidige Architectuur Analyse

De huidige applicatie bevat al sterke fundamenten voor gestructureerde informatie-extractie, gebouwd op **Clean Architecture** principes:

1.  **Duidelijke Ontologie-structuur**: Via de `OntologyRepository` en `ontology-api.ts` is er een flexibele, hiërarchische ontologie (concepten, overerving, mixins en embedded types).
2.  **Ports & Adapters voor LLM's**: De `LLMClient` abstraheert de interactie met modellen (zoals via OpenRouter). Er wordt slim gebruik gemaakt van *tool-calling* (bijvoorbeeld `get_extraction_schema` en `submit_document`).
3.  **Template-Driven Extractie**: In `MetadataExtractionService` worden dynamisch templates opgebouwd (inclusief parent en mixin properties) en naar het LLM gestuurd voor gerichte extractie. 
4.  **Normalisatie**: Er is robuuste regex- en logica-gebaseerde normalisatie voor datums en numerieke waarden (Nederlands/Engels).

**Wat nog ontbreekt (Gap Analysis):**
*   **Vector Embeddings**: Er worden momenteel geen semantische embeddings gegenereerd van de ongestructureerde tekst of metadata, waardoor puur conceptuele zoekopdrachten (vrije tekst) lastig zijn.
*   **Relatie-extractie (Graph)**: Hoewel de ontologie *relaties* definieert (via `ConceptRelationship`), richt het huidige extractieproces (`LLMExtractionResponse`) zich primair op *properties* (key-value metadata structuur in JSONB). Dwarsverbanden ("Persoon X werkt voor Bedrijf Y in Document Z") worden niet als expliciete graaf-entiteiten opgeslagen of herbruikt.
*   **Generation (RAG)**: Het ophalen van informatie gebeurt primair via database queries op properties. Er is geen Retrieval-Augmented Generation (RAG) pijplijn die de opgehaalde documenten en metadata combineert om complexe vragen in natuurlijke taal te beantwoorden.

---

## 3. Theoretische Achtergrond & Best Practices

Om de kloof tussen documentopslag en een proactieve kennisbank te overbruggen, leunen we op patronen uit de *Semantic Web* en *Generative AI* literatuur.

### 3.1 Ontology-Based Information Extraction (OBIE)
OBIE maakt gebruik van formele ontologieën als blauwdruk voor Natural Language Processing pipelines. In plaats van een LLM vrijelijk entiteiten te laten bedenken (Open IE), forceert OBIE het LLM om data te mappen naar de goedgekeurde klasses, attributen en relaties. Dit minimaliseert hallucinaties en garandeert data-uniformiteit.

**Best Practice**: Gebruik **Schema-Aware Prompting**. Dit betekent dat je bij elke prompt niet alleen een tekst meegeeft, maar ook het verwachte JSON Schema (gebaseerd op je ontologie). Moderne modellen (zoals GPT-4o, Claude 3 of recente Gemini modellen) presteren drastisch beter (Structured Outputs) wanneer dit strak gedefinieerd is.

### 3.2 Knowledge Graphs & GraphRAG
Traditionele RAG verdeelt documenten in brokken (chunks), maakt er vector embeddings van en zoekt de meest gerelateerde chunks bij een zoekopdracht. Dit werkt slecht wanneer context verdeeld is over meerdere documenten (bijv: "Wie is de manager van het team dat project X uitvoert?").

*GraphRAG* combineert de ontologie met de vector database. 
1. Het document wordt geëxtraheerd in een graaf (Conceptnodes en -relaties).
2. Vragen (queries) wandelen door deze graaf om indirecte verbindingen te vinden, en halen daarna pas de tekst op. Dit biedt ongekende contextuele accuraatheid.

### 3.3 Human-in-the-Loop (HITL)
Hoewel LLM's consistent beter worden, blijken organisaties voor bedrijfskritische data een vorm van review nodig te hebben. 
**Best Practice**: LLM extracties hebben altijd een "confidence score". Alle concepten met een zekerheid onder een bepaalde drempel (bijv. 80%) worden in een "Te Reviewen" queue geplaatst voor domeinexperts. Het huidige systeem heeft `confidence` velden, maar de actieve HITL-workflow hiervoor moet uitgebouwd worden.

---

## 4. Roadmap met Verbeterpunten

Om van de huidige staat naar het gewenste doel te groeien, volgt hier een uitgewerkte roadmap gericht op backend en AI-integratie.

### Fase 1: Van Properties naar Graafrelaties (Relationele Extractie)
*Huidige situatie*: Het systeem slaat properties op als geïsoleerde JSONB metadata naast het document.
*Verbetering*:
1.  **Relationele Extraction Workflow**: Breid de `MetadataExtractionService` uit zodat de LLM (bij de tool-call `submit_document`) niet alleen `extracted_properties` levert, maar ook expliciete koppelingen (bijv. `extracted_relationships: [{"type": "werkgever", "target_concept_id": "Organization", "target_name": "OpenAI"}]`).
2.  **Identiteit Resolutie**: Ontwikkel een "Entity Resolution Service". Als het LLM "Google LLC" vindt in Document A en "Google" in Document B, moet het systeem dit ontdubbelen en wijzen naar dezelfde Ontologische entiteit.

### Fase 2: Semantisch Zoeken implementeren (Vector Store)
*Huidige situatie*: Full-text en metadata queries via PostgreSQL/SQLAlchemy.
*Verbetering*:
1.  **Chunking Strategy**: Documenten moeten worden opgedeeld in logische blokken ("chunks") o.b.v. alinea's of semantische scheidingstekens.
2.  **Embeddings Genereren**: Introduceer een nieuwe port in `LLMClient`: `generate_embeddings(texts: list[str])`. Gebruik modellen zoals `text-embedding-3-large` of `nomic-embed-text`.
3.  **Vector Database (pgvector)**: Sla deze embeddings op. Aangezien we al een solide relationele PostgreSQL basis hebben, is het toevoegen van de `pgvector` extensie een architecturaal propere best practice. Hierdoor kun je SQL JOINs combineren met vector-similariteit (`ORDER BY vector <-> query_vector`).

### Fase 3: De Hybride RAG (Retrieval-Augmented Generation) Pipeline
*Concept*: Het bouwen van een `QuestionAnsweringService` endpoint.
*Verbetering*:
De flow van een organisatiebrede vraag ("Wat zijn de vereisten van het nieuwe security beleid voor externe leveranciers?"):
1.  **Question Understanding (LLM)**: Het LLM herschrijft de user prompt en bepaalt weke *ontologie* concepten relevant zijn (bijv: `SecurityPolicy`, `Vendor`).
2.  **Graph Retrieval**: Zoek in de database naar documenten gemarkeerd als `Vendor` en relaties tot `SecurityPolicy`.
3.  **Semantic Retrieval**: Gebruik pgvector om ongestructureerde paragrafen te vinden die lijken op de vraagstelling.
4.  **Generation (LLM)**: Bundel deze context samen met een referentie (citation) prompt: *"Beantwoord de vraag gebaseerd op de volgende bronnen. Vermeld [document_id] in je antwoord."*
5.  **Output**: De eindgebruiker krijgt een geformuleerd antwoord plus klikbare bronnen (een naadloze UI ervaring).

### Fase 4: Geavanceerde Tooling & Continue Verbetering
1.  **Ontology Evolution Agent**: Laat 's nachts een achtergrondtaak (agent) draaien die clusters van ongestructureerde documenten analyseert en voorstelt: *"Ik zie vaak het veld 'Compliance Officer' terugkomen in deze contracten, zal ik dit als vaste Property aan de ontologie toevoegen?"* (Kan geïntegreerd worden in de bestaande `suggestType` API endpoint).
2.  **Competency Questions Evaluatie**: Ontwikkel een golden dataset van ~50-100 vragen ("Competency Questions" uit de literatuur) die de kennisbank altijd moet kunnen beantwoorden. Monitor of de RAG pipeline regressie vertoont na code deployment.

---

## 5. Conclusie

De bestaande architectuur maakt slim en schoon (Ports/Adapters) gebruik van LLM tool-calling voor het ontleden van complexe documenten naar de ontologie. Om een daadwerkelijke **contextuele kennisbank** te realiseren, is de paradigmaverschuiving nodig van "bestanden met metadata ophalen" naar "door de ontologie en relaties navigeren". 

Door relationele extractie (Fase 1) en vector search (Fase 2) te integreren, en deze te bevragen via een gestructureerde RAG pipeline (Fase 3), wordt het systeem een intelligent orakel dat organisatiebrede patronen en dwarsverbanden transparant maakt.
