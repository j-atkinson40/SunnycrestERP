## FUNERAL_HOME_VERTICAL.md — Funeral Home Vertical Design 

_Planned April 10, 2026 — Build pending_ 

## Strategic Context 

The funeral home vertical is the second tenant preset after manufacturing. It is the entry point for Bridgeable’s financial services layer — invoice factoring for funeral homes is the earliest planned financial services product. 

The FH vertical is also the primary cross-tenant network driver: 

- FH ↔ Manufacturer (vault orders flow automatically from case to manufacturer) 

- FH ↔ Cemetery (family selects plot during arrangement conference via interactive map) 

- FH ↔ Crematory (cremation job flows cross-tenant when crematory is on network) 

- FH ↔ Urn catalog (already built via urn_sales extension) 

Key competitive insight: Existing FH software (Passare, Osiris, Gather, CRaKN, FDMS, SRS Computing) all require the director to manually enter data into form templates. None have AI-captured arrangement conferences. None have live vault personalization. None have cross-tenant network integration. The gap is significant and real. 

## The Four Key Differentiators 

## 1. AI Arrangement Scribe 

Meeting recording → transcript → auto-populated case file → staircase workflow. Director sees a live two-panel UI during the arrangement conference: 

Left panel: Recording controls / live transcript stream 

- Right panel: Case file populating in real time — green checkmarks for extracted fields, amber for low-confidence (director should confirm), red for required fields not yet collected 

The right panel is the director’s live checklist. They can glance over mid-conversation and see exactly which fields still need to be asked about. Eliminates the need to call the family back for missing information. 

## Two modes: 

- Review mode (Phase 1): Recording ends → Scribe processes full transcript → director reviews pre-filled form before moving forward 

- Live mode (Phase 2): Deepgram real-time streaming → fields populate as they’re mentioned. Infrastructure already exists from Call Intelligence. 

## 2. Legacy Personalization Compositor (Family-Facing) 

The manufacturer’s compositor already exists. The FH version extends it: 

- Embedded in the vault selection step — not a separate step. Director uses it as a sales tool. Select a vault → compositor panel slides in automatically. 

- Family sees deceased’s name, dates rendered live on the actual vault being considered 

- Switch vaults → compositor re-renders instantly on the new vault 

- Comparison mode: 2 designs on 1 vault, OR 1 design on 2 vaults, side by side 

- Select → vault + personalization specs locked to case simultaneously 

- Approved selection creates manufacturer order with personalization specs attached — no phone call, no fax, no transcription error 

Personalization fields in case file (feeds compositor directly): 

- `personalization_name_display` — how name should appear (e.g. “John M. Smith”) 

- `personalization_birth_date_display` — format preference (e.g. “March 15, 1942”) 

- `personalization_death_date_display` — format preference 

- Photo/image attachment handled within compositor UI — not captured by Scribe 

## 3. AI Compliance + Audit Intelligence 

For funeral homes the compliance landscape includes: 

- FTC Funeral Rule — GPL price disclosure, itemization requirements, FTC audits funeral homes. `FTCComplianceService` already built. 

- State licensing — funeral director license renewal requirements 

OSHA — bloodborne pathogens (29 CFR 1910.1030) mandatory for FH 

- State vital records — death certificate filing timelines, fines for late filing 

Preneed regulations — state trust/insurance requirements if they sell preneed 

One-prompt audit package: “Prepare me for an FTC audit” → Claude pulls all case files, checks GPL compliance on every itemized statement, verifies required disclosures, generates gap report + complete audit response package. Worth thousands in attorney fees every time it runs. 

Playwright form submissions: EDRS (Electronic Death Registration System) portals, VA benefit forms, state burial permit portals — all pre-filled from case data, director reviews and approves, Playwright submits. 

## 4. Cross-Tenant Network 

See full network architecture in CLAUDE.md key differentiators. FH-specific: 

- Manufacturer: Vault selection creates direct order to manufacturer tenant. Personalization specs included. No manual communication required. 

- Cemetery: Interactive plot map embedded in arrangement conference. Family selects plot, pays via Bridgeable Pay, plot reserved in cemetery’s system instantly. 

- Crematory: Cremation job flows cross-tenant. Identification, authorization, permit tracking all connected. 

## The Staircase Model 

The case is a spiral staircase. Each task is a landing. The director can pause at any landing before continuing. Order is fully configurable per funeral home — drag-and-drop timeline with cards. 

## Default staircase steps (configurable order): 

|Step Key|Name|Domain Table|Notes|
|---|---|---|---|
|`arrangement_conference`|Arrangement<br>Conference|`funeral_cases` +<br>Scribe|AI Scribe captures<br>meeting|
|`vital_statistics`|Vital Statistics|`case_deceased`|Review/confirm<br>death cert fields|
||||NOK signs|
|||||



|||||
|---|---|---|---|
|`authorization`|Authorization|`case_informants`|disposition auth|
|`service_planning`|Service<br>Planning|`case_service`|Date, venue,<br>officiant,<br>pallbearers|
|`obituary`|Obituary|`case_service`|AI drafts from<br>case data|
|`merchandise_vault`|Vault Selection|`case_merchandise`|Includes Legacy<br>Compositor|
|`merchandise_casket`|Casket<br>Selection|`case_merchandise`||
|`merchandise_urn`|Urn Selection|`case_merchandise`|If cremation|
|`cemetery`|Cemetery &<br>Plot|`case_cemetery`|Interactive plot<br>map if on network|
|`cremation`|Cremation|`case_cremation`|Only if cremation<br>disposition|
|`veterans_benefits`|Veterans<br>Benefits|`case_veteran`|VA flag, honors,<br>DD-214|
|`death_certificate`|Death<br>Certificate|`case_disposition`|EDRS pre-fill +<br>Playwright submit|
|`financials`|Financials|`case_financials`|FTC-compliant<br>GPL itemization|
|`aftercare`|Aftercare|—|Follow-up<br>scheduling, grief<br>resources|



Steps that don’t apply to a case (e.g. veterans benefits for a non-veteran, cremation for a burial) are hidden automatically based on case data. The staircase adapts to the case. 

## Configurable Field System 

The problem: Every state has different death certificate requirements. Every funeral home has different workflows. Forcing a fixed field set frustrates directors and creates liability. 

The solution: A master field library of every possible field (~150-200 total). During onboarding: 

1. Director selects their state → system pre-enables all legally required fields for that state’s death certificate 

2. Director answers module questions (veterans? preneed? cremation only?) → relevant field groups enabled 

3. Director reviews and customizes — toggle additional fields, reorder, mark required vs. optional 

4. System generates their arrangement conference form 

5. Scribe only listens for enabled fields. Forms only pull from enabled fields. 

This handles state variation, director preference variation, and FH business model variation all in one architecture. 

**`case_field_config`** table — one record per tenant created during onboarding. Contains JSONB config per domain with enabled/required/label_override/order per field key. 

## Database Schema 

## Table Inventory 

|Table|Created When|Purpose|
|---|---|---|
|`funeral_cases`|Case opened|Spine — case identity + workflow state|
|`case_deceased`|Always with case|All death certificate fields (wide table<br>justified by federal law)|
|`case_informants`|Always — one-to-<br>many|Next of kin, multiple possible|
|`case_service`|Always with case|Service planning|
|`case_disposition`|Always with case|Disposition method + death cert filing|
|`case_merchandise`|Always with case|Casket, vault, urn + compositor specs|
|`case_financials`|Always with case|FTC GPL itemization + payment|
||||



||||
|---|---|---|
|`case_veteran`|Only if veteran|VA benefits, honors, DD-214|
|`case_preneed`|Only if preneed<br>exists|Preneed policy details|
|`case_cemetery`|Only if<br>burial/entombment|Cross-tenant cemetery integration|
|`case_cremation`|Only if cremation|Cross-tenant crematory integration|
|`case_field_config`|Once per FH tenant|Configurable field library|
|`funeral_case_notes`|Ongoing|Scribe extractions + director edits audit<br>trail|
|`casket_products`|Once per FH tenant,<br>per model|FH’s configured casket catalog|



## Total: 14 tables 

## Cross-Tenant FK Pattern 

All four cross-tenant relationships follow identical pattern: 

- Nullable FK to other tenant’s company record 

- Manual entry fallback when network tenant not connected 

- Auto-populated when network tenant is connected 

- Upgrade path: manual → network with zero data migration 

```
case_merchandise.vault_manufacturer_company_id  → manufacturer tenant
case_merchandise.casket_manufacturer_company_id → manufacturer tenant (future Wil
case_cemetery.cemetery_company_id              → cemetery tenant
case_cremation.crematory_company_id            → crematory tenant
case_merchandise.urn_product_id                → urn_products (already built)
```

## SQLAlchemy Models 

**`funeral_cases`** — The Spine 

```
class FuneralCase(Base):
```

```
    __tablename__ = "funeral_cases"
```

```
    id: Mapped[str]                    # UUID
    company_id: Mapped[str]            # FK to companies
    case_number: Mapped[str]           # Auto-generated e.g. "FC-2026-0142"
    director_id: Mapped[str]           # FK to users
    status: Mapped[str]                # active | completed | cancelled | on_hold
    arrangement_location_type: Mapped[str]
    # funeral_home | residence | hospital | other
    arrangement_location_notes: Mapped[Optional[str]]
    arrangement_conference_at: Mapped[Optional[datetime]]
```

```
    # Scribe
    transcript_r2_key: Mapped[Optional[str]]
    transcript_text: Mapped[Optional[str]]
    scribe_status: Mapped[str]         # not_started | recording | processing | c
    scribe_processed_at: Mapped[Optional[datetime]]
```

```
    # Staircase
```

```
    staircase_config: Mapped[Optional[dict]]   # JSONB ordered step list
    current_step: Mapped[Optional[str]]
    completed_steps: Mapped[Optional[list]]    # JSONB array of completed step ke
```

```
    # Quick flags
    preneed_exists: Mapped[bool]
```

```
    # Cross-tenant denormalized for quick access
    manufacturer_company_id: Mapped[Optional[str]]
    cemetery_company_id: Mapped[Optional[str]]
    crematory_company_id: Mapped[Optional[str]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_deceased`** — Wide Table (Justified by Federal Law) 

```
class CaseDeceased(Base):
    __tablename__ = "case_deceased"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique — one-to-one
    company_id: Mapped[str]
    # Legal name
    first_name: Mapped[Optional[str]]
    middle_name: Mapped[Optional[str]]
```

```
    last_name: Mapped[Optional[str]]
    suffix: Mapped[Optional[str]]
    preferred_name: Mapped[Optional[str]]  # For obituary/service use
```

```
    # Death
    date_of_death: Mapped[Optional[date]]
    time_of_death: Mapped[Optional[time]]
    place_of_death_type: Mapped[Optional[str]]
    # hospital | er_doa | home | hospice_facility | nursing_home | other_facility
    place_of_death_name: Mapped[Optional[str]]
    place_of_death_address: Mapped[Optional[str]]
    place_of_death_city: Mapped[Optional[str]]
    place_of_death_county: Mapped[Optional[str]]
    place_of_death_state: Mapped[Optional[str]]
    # Birth
    date_of_birth: Mapped[Optional[date]]
    age_at_death: Mapped[Optional[int]]    # Auto-calculated
    birthplace_city: Mapped[Optional[str]]
    birthplace_state: Mapped[Optional[str]]
    birthplace_country: Mapped[Optional[str]]
```

```
    # Identity
    ssn: Mapped[Optional[str]]             # ENCRYPTED AT REST — most sensitive f
    sex: Mapped[Optional[str]]             # male | female | unknown
    gender_identity: Mapped[Optional[str]] # Some states require
    marital_status: Mapped[Optional[str]]
    # married | widowed | divorced | never_married | unknown
    surviving_spouse_name: Mapped[Optional[str]]
```

```
    # Residence
    residence_address: Mapped[Optional[str]]
    residence_apt: Mapped[Optional[str]]
    residence_city: Mapped[Optional[str]]
    residence_county: Mapped[Optional[str]]
    residence_state: Mapped[Optional[str]]
    residence_zip: Mapped[Optional[str]]
    residence_country: Mapped[Optional[str]]
    residence_inside_city_limits: Mapped[Optional[bool]]
    years_at_residence: Mapped[Optional[int]]
    # Origins — required for death certificate
    hispanic_origin: Mapped[Optional[str]]        # CDC standard categories
    hispanic_origin_specified: Mapped[Optional[str]]
    race: Mapped[Optional[list]]                  # JSONB — can be multiple
    race_specified: Mapped[Optional[str]]
```

```
    # Biography
    education_level: Mapped[Optional[str]]        # CDC standard categories
    usual_occupation: Mapped[Optional[str]]
    kind_of_business_industry: Mapped[Optional[str]]
    years_in_occupation: Mapped[Optional[int]]
```

```
    # Parents — required for death certificate
    father_first_name: Mapped[Optional[str]]
    father_last_name: Mapped[Optional[str]]
    father_birthplace: Mapped[Optional[str]]
    mother_first_name: Mapped[Optional[str]]
    mother_maiden_name: Mapped[Optional[str]]
    mother_birthplace: Mapped[Optional[str]]
```

```
    # Veteran flag
```

```
    ever_in_armed_forces: Mapped[Optional[bool]]
```

```
    # Legacy Compositor personalization — feeds compositor directly
    personalization_name_display: Mapped[Optional[str]]
    personalization_birth_date_display: Mapped[Optional[str]]
    personalization_death_date_display: Mapped[Optional[str]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_informants`** — One-to-Many 

```
class CaseInformant(Base):
    __tablename__ = "case_informants"
    id: Mapped[str]
    case_id: Mapped[str]               # FK to funeral_cases
    company_id: Mapped[str]
    is_primary: Mapped[bool]           # Primary NOK — authorization signatory
    is_arrangement_contact: Mapped[bool]
    first_name: Mapped[Optional[str]]
    last_name: Mapped[Optional[str]]
    relationship: Mapped[Optional[str]]
    # spouse | child | parent | sibling | other_family | friend | other
    address: Mapped[Optional[str]]
    city: Mapped[Optional[str]]
    state: Mapped[Optional[str]]
    zip: Mapped[Optional[str]]
```

```
    phone_primary: Mapped[Optional[str]]
    phone_alternate: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
```

```
    # Authorization
    authorization_signed: Mapped[bool]
    authorization_signed_at: Mapped[Optional[datetime]]
    authorization_method: Mapped[Optional[str]]
    # in_person | electronic | verbal (flagged) | mailed
    created_at: Mapped[datetime]
```

## **`case_service`** — Service Planning 

```
class CaseService(Base):
    __tablename__ = "case_service"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]
    service_type: Mapped[Optional[str]]
    # funeral | memorial | graveside | celebration_of_life | none
    # Visitation
    visitation: Mapped[bool]
    visitation_date: Mapped[Optional[date]]
    visitation_start_time: Mapped[Optional[time]]
    visitation_end_time: Mapped[Optional[time]]
    visitation_location: Mapped[Optional[str]]
    # Service
    service_date: Mapped[Optional[date]]
    service_time: Mapped[Optional[time]]
    venue_type: Mapped[Optional[str]]
    # funeral_home_chapel | church | cemetery | graveside | residence | other
    venue_name: Mapped[Optional[str]]
    venue_address: Mapped[Optional[str]]
    # Participants
    officiant_name: Mapped[Optional[str]]
    officiant_contact: Mapped[Optional[str]]
    officiant_type: Mapped[Optional[str]]   # clergy | celebrant | family | other
    eulogy_by: Mapped[Optional[str]]
    pallbearers: Mapped[Optional[list]]     # JSONB array
```

```
    honorary_pallbearers: Mapped[Optional[list]]
```

```
    # Service details
    music_selections: Mapped[Optional[list]]
    readings: Mapped[Optional[list]]
    flowers_requested: Mapped[Optional[bool]]
    flowers_notes: Mapped[Optional[str]]
    memorial_donations_to: Mapped[Optional[str]]
    procession: Mapped[bool]
    procession_notes: Mapped[Optional[str]]
    military_honors: Mapped[bool]
    livestream: Mapped[bool]
    special_requests: Mapped[Optional[str]]
    # Obituary
    obituary_drafted: Mapped[bool]
    obituary_text: Mapped[Optional[str]]       # AI drafted, director edits
    obituary_approved: Mapped[bool]
    obituary_submitted_to: Mapped[Optional[list]]  # JSONB — newspapers/sites
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_disposition`** — Disposition + Death Certificate 

```
class CaseDisposition(Base):
    __tablename__ = "case_disposition"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]
    method: Mapped[Optional[str]]
    # burial | cremation | entombment | donation | aquamation | other
    # Funeral home info — auto-filled from tenant
    funeral_home_name: Mapped[Optional[str]]
    funeral_home_address: Mapped[Optional[str]]
    funeral_home_license_number: Mapped[Optional[str]]
    funeral_director_name: Mapped[Optional[str]]
    funeral_director_license_number: Mapped[Optional[str]]
```

```
    # Body preparation
    embalming_authorized: Mapped[Optional[bool]]
    embalming_performed: Mapped[Optional[bool]]
```

```
    clothing_description: Mapped[Optional[str]]
    glasses: Mapped[Optional[bool]]
    jewelry_notes: Mapped[Optional[str]]
    photo_provided: Mapped[Optional[bool]]
```

```
    # Death certificate
    death_certificate_number: Mapped[Optional[str]]
    death_certificate_filed_at: Mapped[Optional[datetime]]
    death_certificate_copies_ordered: Mapped[Optional[int]]
    edrs_state: Mapped[Optional[str]]
    edrs_submitted_at: Mapped[Optional[datetime]]
    edrs_confirmed_at: Mapped[Optional[datetime]]
```

```
    # Burial permit
    burial_permit_number: Mapped[Optional[str]]
    burial_permit_issued_at: Mapped[Optional[datetime]]
    burial_permit_jurisdiction: Mapped[Optional[str]]
```

```
    # Transit permit
    transit_permit_required: Mapped[bool]
    transit_permit_number: Mapped[Optional[str]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_merchandise`** — Vault + Casket + Urn + Compositor 

```
class CaseMerchandise(Base):
    __tablename__ = "case_merchandise"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]
    # Casket
    casket_product_id: Mapped[Optional[str]]     # FK to casket_products
    casket_name: Mapped[Optional[str]]           # Denormalized for case record
    casket_price: Mapped[Optional[float]]
    casket_supplier: Mapped[Optional[str]]       # batesville | matthews | wilber
    casket_supplier_model_number: Mapped[Optional[str]]  # Supplier's SKU for ord
    casket_manufacturer_company_id: Mapped[Optional[str]]  # Future Wilbert cross
    casket_order_placed_at: Mapped[Optional[datetime]]
    casket_order_confirmation: Mapped[Optional[str]]  # Captured from supplier po
    casket_order_status: Mapped[Optional[str]]   # pending | ordered | confirmed
```

```
    # Vault — cross-tenant to manufacturer
    vault_product_id: Mapped[Optional[str]]
    vault_name: Mapped[Optional[str]]
    vault_price: Mapped[Optional[float]]
    vault_manufacturer_company_id: Mapped[Optional[str]]  # FK to manufacturer te
    vault_order_id: Mapped[Optional[str]]       # FK to manufacturer sales_orders
    vault_order_status: Mapped[Optional[str]]   # pending | confirmed | delivered
    # Legacy Compositor
    compositor_design_id: Mapped[Optional[str]]
    compositor_snapshot_r2_key: Mapped[Optional[str]]
    compositor_approved_at: Mapped[Optional[datetime]]
    compositor_approved_by: Mapped[Optional[str]]
    # Urn — if cremation
    urn_product_id: Mapped[Optional[str]]       # FK to urn_products
    urn_name: Mapped[Optional[str]]
    urn_price: Mapped[Optional[float]]
    urn_order_id: Mapped[Optional[str]]         # FK to urn_orders
    urn_personalization_notes: Mapped[Optional[str]]
    # Other
    outer_burial_container_id: Mapped[Optional[str]]
    memorial_items: Mapped[Optional[list]]      # JSONB
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_financials`** — FTC GPL + Payment 

```
class CaseFinancials(Base):
    __tablename__ = "case_financials"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]
    # FTC Funeral Rule — GPL itemization
    # JSONB line items: {category, description, amount, required_disclosure}
    statement_of_goods_services: Mapped[Optional[dict]]
    # Totals
    subtotal: Mapped[Optional[float]]
    cash_advance_total: Mapped[Optional[float]]
    total: Mapped[Optional[float]]
```

```
    amount_paid: Mapped[Optional[float]]
    balance_due: Mapped[Optional[float]]
```

```
    # Payment
    payment_method: Mapped[Optional[str]]
    # cash | check | credit_card | insurance | preneed | combination
    # Insurance assignment
    insurance_assignment: Mapped[bool]
    insurance_company: Mapped[Optional[str]]
    insurance_policy_number: Mapped[Optional[str]]
    insurance_amount: Mapped[Optional[float]]
    insurance_assignment_confirmed: Mapped[bool]
```

```
    # FTC compliance
    gpl_provided_at_first_contact: Mapped[Optional[bool]]
    gpl_version_id: Mapped[Optional[str]]      # FK to price_list_versions
    ftc_disclosures_made: Mapped[bool]
```

```
    # Statement status
    statement_generated_at: Mapped[Optional[datetime]]
    statement_approved_at: Mapped[Optional[datetime]]
    statement_sent_at: Mapped[Optional[datetime]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_veteran`** — Only if Veteran 

```
class CaseVeteran(Base):
    __tablename__ = "case_veteran"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]
    branch_of_service: Mapped[Optional[str]]
    # army | navy | air_force | marine_corps | coast_guard |
    # space_force | national_guard | reserves
    service_start_date: Mapped[Optional[date]]
    service_end_date: Mapped[Optional[date]]
    discharge_type: Mapped[Optional[str]]
    rank: Mapped[Optional[str]]
    war_period: Mapped[Optional[str]]
    va_claim_number: Mapped[Optional[str]]
```

```
    dd214_on_file: Mapped[bool]
```

```
    # Benefits
    va_flag_requested: Mapped[bool]
    presidential_certificate_requested: Mapped[bool]
    military_honors_requested: Mapped[bool]
    honors_type: Mapped[Optional[str]]         # full | graveside | other
    national_cemetery_burial: Mapped[bool]
```

```
    # Filing status
    va_flag_submitted_at: Mapped[Optional[datetime]]
    va_flag_confirmed: Mapped[bool]
    honors_confirmed_at: Mapped[Optional[datetime]]
    honors_unit: Mapped[Optional[str]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_preneed`** — Only if Preneed Policy Exists 

```
class CasePreneed(Base):
    __tablename__ = "case_preneed"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]
```

```
    policy_number: Mapped[Optional[str]]
    issuing_funeral_home: Mapped[Optional[str]]
    insurance_company: Mapped[Optional[str]]
    policy_amount: Mapped[Optional[float]]
    policy_verified: Mapped[bool]
    policy_applied_to_balance: Mapped[bool]
```

```
    preplanned_service_type: Mapped[Optional[str]]
    preplanned_casket: Mapped[Optional[str]]
    preplanned_disposition: Mapped[Optional[str]]
    preplanned_notes: Mapped[Optional[str]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_cemetery`** — Cross-Tenant Cemetery Integration 

```
class CaseCemetery(Base):
    __tablename__ = "case_cemetery"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]            # FK to FH tenant
    # Cemetery
    cemetery_company_id: Mapped[Optional[str]]  # FK to cemetery tenant if on net
    cemetery_name: Mapped[Optional[str]]
    cemetery_address: Mapped[Optional[str]]
    cemetery_city: Mapped[Optional[str]]
    cemetery_state: Mapped[Optional[str]]
    cemetery_contact_name: Mapped[Optional[str]]
    cemetery_contact_phone: Mapped[Optional[str]]
    # Plot / Niche
    plot_id: Mapped[Optional[str]]              # FK to cemetery plot inventory i
    plot_section: Mapped[Optional[str]]
    plot_row: Mapped[Optional[str]]
    plot_number: Mapped[Optional[str]]
    plot_type: Mapped[Optional[str]]
    # single | double | cremation_niche | mausoleum | green | other
    plot_reserved_at: Mapped[Optional[datetime]]
    plot_payment_status: Mapped[Optional[str]]  # pending | paid | prepaid
    plot_payment_amount: Mapped[Optional[float]]
    plot_payment_transaction_id: Mapped[Optional[str]]  # Bridgeable Pay referenc
    # Interment
    interment_date: Mapped[Optional[date]]
    interment_time: Mapped[Optional[time]]
    interment_coordinator: Mapped[Optional[str]]
    entombment_location: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## **`case_cremation`** — Cross-Tenant Crematory Integration 

```
class CaseCremation(Base):
    __tablename__ = "case_cremation"
    id: Mapped[str]
    case_id: Mapped[str]               # FK unique
    company_id: Mapped[str]            # FK to FH tenant
```

```
    # Crematory
    crematory_company_id: Mapped[Optional[str]]  # FK to crematory tenant if on n
    crematory_name: Mapped[Optional[str]]
    crematory_address: Mapped[Optional[str]]
    crematory_license_number: Mapped[Optional[str]]
    crematory_contact_name: Mapped[Optional[str]]
    crematory_contact_phone: Mapped[Optional[str]]
```

```
    # Authorization — legally required before cremation
    cremation_authorized: Mapped[bool]
    cremation_authorized_at: Mapped[Optional[datetime]]
    cremation_authorized_by: Mapped[Optional[str]]
    authorization_form_r2_key: Mapped[Optional[str]]
```

```
    # Cremation permit
    cremation_permit_number: Mapped[Optional[str]]
    cremation_permit_issued_at: Mapped[Optional[datetime]]
    cremation_permit_jurisdiction: Mapped[Optional[str]]
```

```
    # Medical examiner clearance
    me_clearance_required: Mapped[bool]
    me_clearance_obtained: Mapped[bool]
    me_case_number: Mapped[Optional[str]]
```

```
    # Identifying disc
    identifying_disc_number: Mapped[Optional[str]]
    identifying_disc_confirmed: Mapped[bool]
```

```
    # Cross-tenant cremation job
    cremation_job_id: Mapped[Optional[str]]      # FK to crematory tenant job rec
    cremation_job_status: Mapped[Optional[str]]  # pending | scheduled | complete
```

```
    # Timing
    cremation_scheduled_at: Mapped[Optional[datetime]]
    cremation_completed_at: Mapped[Optional[datetime]]
```

```
    # Remains
    remains_weight_lbs: Mapped[Optional[float]]
    remains_returned_at: Mapped[Optional[datetime]]
    remains_disposition: Mapped[Optional[str]]
    # urn_burial | urn_entombment | scattering | kept_by_family | divided | other
    remains_disposition_notes: Mapped[Optional[str]]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**`case_field_config`** — Per-Tenant Field Configuration 

```
class CaseFieldConfig(Base):
    __tablename__ = "case_field_configs"
    id: Mapped[str]
    company_id: Mapped[str]            # FK unique — one per FH tenant
    state: Mapped[Optional[str]]       # State pre-set applied at onboarding
```

```
    # JSONB config per domain
    # Structure: {"field_key": {"enabled": bool, "required": bool,
    #              "label_override": str|None, "order": int}}
    deceased_fields: Mapped[Optional[dict]]
    informant_fields: Mapped[Optional[dict]]
    service_fields: Mapped[Optional[dict]]
    disposition_fields: Mapped[Optional[dict]]
    merchandise_fields: Mapped[Optional[dict]]
    cemetery_fields: Mapped[Optional[dict]]
    veteran_fields: Mapped[Optional[dict]]
    preneed_fields: Mapped[Optional[dict]]
    financial_fields: Mapped[Optional[dict]]
    cremation_fields: Mapped[Optional[dict]]
```

```
    # Default staircase step order for this tenant
    default_staircase_config: Mapped[Optional[list]]  # JSONB ordered step list
```

```
    # Module toggles
```

```
    veterans_module_enabled: Mapped[bool]
    preneed_module_enabled: Mapped[bool]
    cemetery_network_enabled: Mapped[bool]
    crematory_network_enabled: Mapped[bool]
    compositor_enabled: Mapped[bool]
```

```
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**`funeral_case_notes`** — Audit Trail 

```
class FuneralCaseNote(Base):
    __tablename__ = "funeral_case_notes"
    id: Mapped[str]
    case_id: Mapped[str]               # FK to funeral_cases
    company_id: Mapped[str]
    user_id: Mapped[Optional[str]]     # Null if system/scribe
```

```
    note_type: Mapped[str]
    # scribe_extraction | director_edit | family_update |
```

```
    # system | call | email | sms
```

```
    content: Mapped[str]
```

```
    field_key: Mapped[Optional[str]]   # If note is about a specific field change
    old_value: Mapped[Optional[str]]
    new_value: Mapped[Optional[str]]
    scribe_confidence: Mapped[Optional[float]]  # If scribe extraction
```

```
    created_at: Mapped[datetime]
```

## Arrangement Conference Intake — Three Methods 

The arrangement conference case file can be populated via any of the three platformstandard intake methods. All three share the same right-panel completion UI. The director chooses their method at the top of the arrangement conference screen — Method 1 is presented most prominently, Method 3 least. 

## Shared UI — The Live Completion Panel (Right Panel, All Methods) 

Identical across all three methods. Shows case file completion status by domain, updating in real time regardless of how data is entering the system: 

**==> picture [13 x 13] intentionally omitted <==**

```
 Case #FC-2026-0142 — John Michael Smith
```

```
DECEASED INFO          ████████████░░  18/22 fields   4 missing
SERVICE PLANNING       ██████░░░░░░░░   6/14 fields   8 missing
VETERAN BENEFITS       ░░░░░░░░░░░░░░   0/8  fields   Not started
DISPOSITION            ████████████░░  11/12 fields   1 missing
MERCHANDISE            ░░░░░░░░░░░░░░   0/6  fields  ○  Not yet
```

## Field status indicators: 

**==> picture [15 x 15] intentionally omitted <==**

Green — captured with high confidence 

**==> picture [15 x 15] intentionally omitted <==**

Amber — captured, low confidence, director should confirm 

**==> picture [15 x 15] intentionally omitted <==**

Red — required field, not yet collected 

- Gray — optional, not yet collected 

Each missing field is tappable — takes director directly to that field in the form. The panel is the director’s live checklist regardless of which method they use. 

## Method 1 — AI Arrangement Scribe 

Left panel: Recording controls + live transcript stream 

The director records the arrangement conference. The Scribe processes the transcript against the tenant’s enabled field list and populates the completion panel in real time (live mode) or after the recording ends (review mode). 

## Two sub-modes: 

_Review mode (Phase 1):_ Recording ends → Scribe processes full transcript → completion panel populates → director reviews before moving forward on staircase. 

_Live mode (Phase 2):_ Deepgram real-time streaming → fields populate as they’re mentioned during the conversation → director sees the completion panel updating live alongside the meeting. Infrastructure already exists via Call Intelligence. 

## Method 2 — Natural Language Input 

Left panel: A single text input field (with microphone button if permission granted) where the director types or speaks what they know in plain English as they go — before, during, or after a call or meeting. 

The director types a sentence or a few notes, hits enter, and Claude parses the input against enabled fields. The completion panel updates immediately showing what was extracted. 

## Example: 

```
Director types: "John Michael Smith, born March 3 1942, died yesterday at
St. Joseph's Hospital, Catholic, retired steelworker, survived by wife Mary
and three children, wants burial at St. Mary's"
```

```
Panel updates instantly:
 deceased_first_name — John
 deceased_middle_name — Michael
 deceased_last_name — Smith
 date_of_birth — March 3, 1942
 date_of_death — [today - 1]
 place_of_death_name — St. Joseph's Hospital
```

**==> picture [13 x 12] intentionally omitted <==**

```
 religion — Catholic
 usual_occupation — Steelworker (retired)
 surviving_spouse_name — Mary
 disposition_preference — Burial
 cemetery_preference — St. Mary's
 number_of_children — 3 (confirm exact names?)
```

**==> picture [13 x 13] intentionally omitted <==**

**==> picture [13 x 13] intentionally omitted <==**

**==> picture [13 x 13] intentionally omitted <==**

**==> picture [13 x 13] intentionally omitted <==**

**==> picture [13 x 12] intentionally omitted <==**

The director keeps typing as they learn more — each entry adds to the previous extractions. The panel shows cumulative state, not just what the last input contained. 

Voice input: When microphone permission is granted, the microphone button activates browser Web Speech API for dictation into the same text field. Director speaks naturally, text appears, Claude processes on submit. Falls back gracefully to text-only if permission denied. 

Design principle: The text input field should feel like a notepad, not a search box. It accepts fragments, full sentences, bullet points, whatever the director naturally produces when taking notes. Claude handles the parsing — the director doesn’t need to think about field names or structure. 

## Method 3 — Standard Form Entry 

Left panel: Traditional field-by-field form organized by domain section (Deceased, Service, Disposition, etc.). 

Always available. Never the first thing the director sees — presented as “Fill out manually” as a text link below the Method 1 and Method 2 options, not a prominent button. Visual hierarchy makes the AI paths feel like less work without hiding anything. 

The completion panel on the right still updates as fields are filled — so even manual entry benefits from the same progress visibility. Required fields missing at the end of a section are highlighted before the director can advance on the staircase. 

## Method Selection UI 

At the top of the arrangement conference screen, three options presented with clear visual hierarchy: 

```
How would you like to capture arrangement details?
```

```
[ Record Arrangement Conference]   ← Primary — large, prominent
[ Type or speak as you go]         ← Secondary — medium prominence
```

```
                Fill out manually ↓   ← Tertiary — text link only
```

The director can switch methods at any time mid-session. Data already captured is preserved regardless of which method captured it — all three methods write to the same case file fields. 

## UI/UX Design Philosophy 

## The Two Modes of a Funeral Director 

Funeral directors operate in two fundamentally different modes: 

Mode 1 — Funeral Direction (their identity, their purpose) Everything about cases and families. Arrangement conferences, staircase progression, service planning, family communication, vault and casket selection, cemetery coordination. This is why they became funeral directors. 

Mode 2 — Business Management (what they have to tolerate) Financials, compliance, marketing, staff management, reporting. Necessary but not why they showed up today. 

The UI must honor this distinction. Case management is front and center. Business management is one tap away but never in their face by default. A funeral director should be able to go from login to case entry without ever thinking about AR aging or FTC compliance unless they choose to. 

## Two Hubs 

Hub 1 — Funeral Direction (default home) The home screen every director sees when they log in. Cases, families, services, arrangements. Everything designed around getting to case work as fast as possible. 

Hub 2 — Business Management (secondary, one tap away) Financials, compliance, website/marketing, staff, reporting. A fully designed dashboard in its own right — just not the default. When a director needs to deal with business stuff it should be just as efficient as the case side. The distinction is about default attention, not quality. 

The widget bridge: Directors who want business data on their home dashboard can add it as widgets — opt-in, not default. A director who monitors daily revenue can surface that. A director who just wants to do funeral work never sees it unless they choose to. Widget categories: 

- _Case Management widgets_ — today’s services, pending authorizations, active case count, needs-attention items 

- _Business widgets_ — balance due summary, compliance status, GPL last updated, website traffic 

Role-based defaults: The default home hub is role-configurable: 

- Funeral directors → Funeral Direction hub by default 

- Office managers / bookkeepers → Business Management hub by default 

- Owner/admin → configurable, defaults to Funeral Direction 

## Navigation Between Hubs 

Never buried. A persistent bottom nav on mobile or top-level tab on desktop. Not a 

hamburger menu, not a settings screen. Business hub feels right there when you need it — just not in your face when you don’t. 

```
Mobile bottom nav:
[  Home ] [  Cases ] [  Services ] [  Business ] [  ]
Desktop top nav:
Bridgeable    [ Cases ]  [ Services ]  [ Business ▾ ]      Michael
```

## Hub 1 — Funeral Direction Home Dashboard 

Goal: Zero friction to case entry. A director logging in is in one of three states — starting a new case, following up on an active case, or acting on something that needs attention. All three completable in one tap. 

**==> picture [476 x 167] intentionally omitted <==**

**----- Start of picture text -----**<br>
┌─────────────────────────────────────────────────────────────┐<br>│  Good morning, Michael.                                 │<br>├─────────────────────────────────────────────────────────────┤<br>│                                                             │<br>│  ┌─────────────────────────────────────────────────────┐   │<br>│  │              + New Arrangement                      │   │<br>│  └─────────────────────────────────────────────────────┘   │<br>│                                                             │<br>│  ┌──────────────────────────────────────────────────────┐  │<br>│  │     Search cases, families, staff...                │  │<br>**----- End of picture text -----**<br>


**==> picture [476 x 420] intentionally omitted <==**

**----- Start of picture text -----**<br>
│  └──────────────────────────────────────────────────────┘  │<br>│                                                             │<br>│  NEEDS ATTENTION                                            │<br>│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │<br>│  │   3 Forms   │ │   2 Proofs  │ │   1 Auth    │        │<br>│  │ ready to     │ │ awaiting     │ │ unsigned     │        │<br>│  │ submit       │ │ approval     │ │              │        │<br>│  └──────────────┘ └──────────────┘ └──────────────┘        │<br>│                                                             │<br>▾<br>│  ACTIVE CASES                              Sort: Recent     │<br>│  ┌─────────────────────────────────────────────────────┐   │<br>│  │ John Smith          Step: Vault Selection    Day 2  │   │<br>│  │ Mary Johnson        Step: Death Certificate  Day 5  │   │<br>│  │ Robert Chen         Step: Service Planning   Day 1  │   │<br>│  │ Eleanor Davis       Step: Financials         Day 8  │   │<br>│  │ + 3 more                                            │   │<br>│  └─────────────────────────────────────────────────────┘   │<br>│                                                             │<br>│  THIS WEEK                                                  │<br>│  ┌─────────────────────────────────────────────────────┐   │<br>│  │ Today    2:00pm  Smith service — First Baptist       │   │<br>│  │ Today    4:30pm  Johnson visitation — Chapel A       │   │<br>│  │ Tomorrow 10:00am Chen arrangement conference        │   │<br>│  └─────────────────────────────────────────────────────┘   │<br>│                                                             │<br>│  [+ Add business widget]          ← opt-in, bottom of page │<br>└─────────────────────────────────────────────────────────────┘<br>**----- End of picture text -----**<br>


## Design decisions: 

- ”+ New Arrangement” is the hero button — full width, prominent, first thing after the greeting. When a family calls at 11pm this is the only button the director should have to think about 

- Search is second — instant, full-text, searches case names, family names, case numbers, phone numbers 

- Needs Attention is third — not a notification drawer, visible action cards showing exactly what requires a response right now. Direct links to the specific item 

- Active cases list is fourth — current staircase step and case age visible at a glance. Tapping any row opens the case dashboard instantly 

- This week is last — upcoming services and events, relevant but not urgent 

- ”+ Add business widget” at the very bottom — the opt-in mechanism for directors who want business data on this screen, positioned so it never intrudes on directors who 

don’t 

Deliberately absent from default view: Analytics, revenue charts, AR aging, compliance scores. Those live in the Business Hub. Directors who want them here add them as widgets. 

## The Case Dashboard 

The center of everything. Once inside a case the director needs an elegant overview that answers every quick question at a glance and lets them act without drilling into subpages. 

Philosophy: Status surface + quick action launcher. Full detail pages exist for each domain but the director should rarely need them for routine checks. 

**==> picture [476 x 503] intentionally omitted <==**

**----- Start of picture text -----**<br>
┌─────────────────────────────────────────────────────────────┐<br>│ ← Cases                                          FC-2026-142 │<br>├─────────────────────────────────────────────────────────────┤<br>│                                                             │<br>│  JOHN MICHAEL SMITH                                         │<br>│  March 3, 1942 — April 9, 2026  ·  Age 84                  │<br>│  Director: Michael Torres  ·  Day 3 of arrangement          │<br>│                                                             │<br>├─────────────────────────────────────────────────────────────┤<br>│  THE STAIRCASE                                              │<br>│                                                             │<br>│    Arrangement      Vital Stats     Authorization         │<br>│    Service          Vault ←HERE  ○ Cemetery               │<br>│  ○ Death Cert      ○ Financials    ○ Aftercare              │<br>│                                                             │<br>│           [Continue: Vault Selection →]                     │<br>├─────────────────────────────────────────────────────────────┤<br>│                                                             │<br>│  ┌─────────────────────┐  ┌─────────────────────┐          │<br>│  │   DECEASED         │  │   SERVICE           │          │<br>│  │ John Michael Smith  │  │ Sat Apr 13, 2:00pm   │          │<br>│  │ DOB: Mar 3, 1942    │  │ First Baptist Church │          │<br>│  │ SSN: •••-••-6789   │  │ Visitation: Fri 5pm  │          │<br>│  │ Veteran: Yes ✓      │  │ Officiant: Fr. Burke │          │<br>│  │ [Edit]              │  │ [Edit]               │          │<br>│  └─────────────────────┘  └─────────────────────┘          │<br>│                                                             │<br>│  ┌─────────────────────┐  ┌─────────────────────┐          │<br>│  │   FAMILY           │  │   MERCHANDISE       │          │<br>│  │ Mary Smith (spouse) │  │ Vault: Pending      │          │<br>│  │   555-0142         │  │ Casket: Batesville   │          │<br>│  │ Auth: Signed       │  │   Heritage — ordered │          │<br>**----- End of picture text -----**<br>


**==> picture [476 x 329] intentionally omitted <==**

**----- Start of picture text -----**<br>
│  │ [Edit]              │  │ [Continue to Vault]  │          │<br>│  └─────────────────────┘  └─────────────────────┘          │<br>│                                                             │<br>│  ┌─────────────────────┐  ┌─────────────────────┐          │<br>│  │   DISPOSITION      │  │   FINANCIALS        │          │<br>│  │ Burial              │  │ Total: $8,450        │          │<br>│  │ St. Mary's Cemetery │  │ Paid: $2,000         │          │<br>│  │ Plot: C-4-12        │  │ Balance: $6,450      │          │<br>│  │ DC: Not filed      │  │ Insurance: Pending   │          │<br>│  │ [Edit]              │  │ [View Statement]     │          │<br>│  └─────────────────────┘  └─────────────────────┘          │<br>│                                                             │<br>│  ┌─────────────────────┐  ┌─────────────────────┐          │<br>│  │   VETERAN          │  │   NOTES             │          │<br>│  │ US Army, 1962-1965  │  │ Scribe: Apr 9       │          │<br>│  │ VA Flag: Requested  │  │ Last: "Family req.   │          │<br>│  │ Honors: Confirmed   │  │  no flowers" Apr 10  │          │<br>│  │ DD-214: On file    │  │ [+ Add Note]         │          │<br>│  └─────────────────────┘  └─────────────────────┘          │<br>│                                                             │<br>└─────────────────────────────────────────────────────────────┘<br>**----- End of picture text -----**<br>


## Design decisions: 

- Staircase always visible near the top — director always knows exactly where this case stands. “Continue” button is one tap to resume 

- Domain cards are scannable — 3-4 most important facts per domain, Edit link always present. Director can answer “when is the service?” without navigating anywhere 

- Cards needing attention have a soft amber border — not a loud alert, just a subtle signal. “DC: Not filed ” draws the eye without demanding action 

- SSN masked by default — tap the icon to reveal for 10 seconds, then re-masks automatically 

- Notes is first-class — directors add notes constantly. Fast capture from the dashboard without navigating away 

- Domain cards that don’t apply are hidden — no Veteran card for non-veterans, no Cremation card for burials. The dashboard adapts to the case 

- Financials card is present but not emphasized — balance information is useful context for a director, but it’s presented at card-scale alongside everything else, not as a prominent dashboard element 

## Hub 2 — Business Management Dashboard 

One tap from the home screen. A fully designed hub in its own right — just not the default. Covers everything a funeral director has to deal with to run their business. 

## Sections: 

- Financials — AR/AP summary, outstanding balances, recent payments, revenue this month 

- Compliance — FTC compliance status, OSHA training status, license expiry dates, audit readiness 

- Website — recent obituary activity, contact form leads, site traffic summary, GPL last updated 

- Staff — director schedules, on-call rotation, certification status 

- Reports — case volume, revenue trends, merchandise margins 

The Business Hub follows the same widget pattern as the manufacturing Operations Board — sections are configurable, can be reordered, can be hidden. An owner sees everything. A part-time director might hide financials entirely. 

## Mobile Design 

Funeral directors are rarely at a desk. They’re at a family’s home, at the hospital, at the cemetery. Mobile is not a responsive shrink — it’s a deliberate separate design. 

## Home screen on mobile: 

- Full-width New Arrangement button 

- Search bar 

- Needs-attention cards (horizontal scroll) 

- Active cases list (name + current step only) 

This week (next 2 events only, “see all” link) 

## Case dashboard on mobile: 

- Staircase condensed to a horizontal progress strip at the top — 

- completed/current/remaining as colored dots 

- Continue button pinned to bottom of screen regardless of scroll position — always 

reachable 

- Domain cards stack vertically, same content as desktop 

Notes card always last — quick capture at bottom 

Navigation: Persistent bottom tab bar — Home, Cases, Services, Business, Profile. Never more than one tap from anywhere to anywhere that matters. 

## The Underlying Principle 

A funeral director should never have to think about where to go. The home screen tells them what needs attention and lets them start something new in one tap. The case dashboard tells them exactly where everything stands and what to do next. Navigation is a last resort, not the primary mode of operation. 

The business of running a funeral home is handled — but it stays out of the way until needed. When it’s needed, it’s one tap away and just as well-designed as everything else. 

## Competitive Landscape 

## Main competitors: Passare, Osiris, Gather, CRaKN, FDMS, SRS Computing 

Key gap across all of them: 

- All require manual data entry into templates 

- None have AI-captured arrangement conferences 

None have live vault personalization with family comparison 

- Passare has EDRS integration in Pennsylvania (closest to Playwright submission) but still requires manual entry first 

None have cross-tenant network integration 

Bridgeable’s position: The director enters nothing. They conduct their meeting. The system handles the rest. 

## Open Items / Research Needed 

HIPAA compliance requirements for case data storage — SSN encryption pattern needs 

to be established as a platform standard 

EDRS system URLs per state — needed for Playwright submission build 

VA benefit portal URLs — Form 27-2008, 40-0247 submission 

State burial permit portal research — which states have online submission 

- Interview actual funeral directors before building — confirm staircase step order defaults, confirm field library completeness, confirm what “configurable” means to them in practice 

Invoice factoring integration point — `case_financials.balance_due` + 

`case_financials.insurance_assignment` are the key fields. FH submits case, 

Bridgeable advances the balance, cemetery/manufacturer get paid immediately. 

## Migration 

When ready to build: migration will be `r16_funeral_home_case_model` (or r17 if urn enrichment agent is built first). 

Revises: `r15_safety_program_generation` 

Creates all 14 tables above (13 original + casket_products). SSN field encrypted at rest — encryption approach to be determined before migration is written. 

## Casket Selection Architecture 

## Strategic Context 

Both major casket suppliers — Batesville and Matthews Aurora — have deliberately built closed software ecosystems tied to their products. Batesville owns Halcyon (FH management software) and Family Choices Digital Showroom. Matthews owns Advisor and their Catalog App. Neither offers a public API for third-party integration. This is their lock-in strategy and they won’t change it. 

This means casket selection cannot be solved through supplier API integration the way vault ordering can. It requires a different approach. 

## Three-Tier Architecture 

Tier 1 — FH’s Own Configured Catalog (Core) 

Every FH configures their own casket catalog in Bridgeable during onboarding — the 20-40 models they actually carry or regularly order. They enter them once. Onboarding makes this fast: 

- Upload a price list CSV, OR 

- Let Claude parse whatever document they currently use (price sheet, Batesville invoice history, etc.) and auto-create catalog entries 

One-time setup, maintained as prices change 

This is the primary selection experience during the arrangement conference — their own curated catalog with images, filterable by material, price, showroom availability. 

## Tier 2 — Playwright Post-Selection Ordering (Automation) 

When a casket is selected from the catalog, a single “Place Order” button launches Playwright to pre-fill the supplier’s ordering portal: 

- Batesville Connect → pre-fill model number, quantity, delivery address, case details 

- Matthews Solution Center → same 

Any other supplier with a web portal → same pattern 

Director reviews the pre-filled form and submits. Order confirmation number captured back to the case. Works for any supplier, not just the two majors. 

This is actually a better experience than Batesville’s own Family Choices showroom — the director’s entire catalog is in one place regardless of supplier, case data is pre-attached, and the ordering automation works universally. 

## Tier 3 — Wilbert Casket Extension (Future Cross-Tenant) 

When the Wilbert casket product line extension is built for manufacturer tenants, it follows the identical cross-tenant pattern as vaults: 

- FH selects Wilbert casket → order flows directly to manufacturer tenant 

- No Playwright needed — native network transaction 

- `casket_manufacturer_company_id` on `case_merchandise` is already nullable and waiting 

- for this FK 

## **`casket_products`** Table — FH’s Configured Catalog 

14th table added to the schema. Per-tenant, one record per casket model the FH sells. 

```
class CasketProduct(Base):
    __tablename__ = "casket_products"
    id: Mapped[str]
    company_id: Mapped[str]            # FK to FH tenant
    name: Mapped[str]
    model_number: Mapped[Optional[str]]   # Supplier's SKU — used for Playwright
    supplier: Mapped[Optional[str]]
    # batesville | matthews | wilbert | other
    material: Mapped[Optional[str]]
    # steel_18g | steel_20g | wood_hardwood | wood_veneer | copper | bronze | oth
    gauge: Mapped[Optional[str]]
    interior_description: Mapped[Optional[str]]
    color: Mapped[Optional[str]]
    price: Mapped[Optional[float]]         # FH's retail price to family
    wholesale_cost: Mapped[Optional[float]]  # FH's cost from supplier
    image_r2_key: Mapped[Optional[str]]
    is_active: Mapped[bool]
    display_order: Mapped[Optional[int]]
    in_showroom: Mapped[bool]              # Physical display vs. catalog-only
    notes: Mapped[Optional[str]]
    # Wilbert cross-tenant (future)
    manufacturer_company_id: Mapped[Optional[str]]  # FK when Wilbert casket ext
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

## Playwright Ordering Supplier Config 

Stored in platform config (not per-tenant) — one entry per supported supplier: 

```
CASKET_SUPPLIER_ORDERING = {
    "batesville": {
        "portal_url": "https://login.batesville.com/",
        "name": "Batesville Connect",
        "field_map": {
            "model_number": "#model-number-input",
            "quantity": "#qty",
            "delivery_address": "#ship-to-address",
            # ... confirmed via Playwright inspection
        }
    },
    "matthews": {
```

```
        "portal_url": "https://apps.matthewsaurora.com/",
```

```
        "name": "Matthews Solution Center",
```

```
        "field_map": { ... }
```

```
    }
```

```
}
```

CSS selectors confirmed via Playwright inspection of live portals before build. FH provides their own supplier login credentials — stored encrypted per tenant, never on Railway in plaintext. 

## Selection UX During Arrangement Conference 

Casket step on the staircase shows: 

- Grid of FH’s configured catalog with product images 

- Filter by: material type, price range, in-showroom vs. catalog-only, supplier 

- Select → name, model number, price locked to `case_merchandise` 

- “Place Order via [Supplier Name]” button appears 

- Playwright pre-fills supplier portal → director reviews → submits 

- Confirmation number auto-captured to `case_merchandise.casket_order_confirmation` 

## Open Items for Casket Build 

- Playwright inspection of Batesville Connect order form to confirm CSS selectors 

- Playwright inspection of Matthews Solution Center order form 

- Onboarding CSV import format for casket catalog 

- Claude-powered catalog import (parse existing price sheet → create casket_products) 

- Wilbert casket extension design (manufacturer side) — future session 

## Tenant Website Builder 

## Strategic Position 

Funeral home software competitors (Batesville WebLink, FrontRunner, Tribute Technology) all provide websites as part of their offering. Bridgeable must match this at minimum and exceed it through the case file integration advantage. 

The website builder is built as a cross-vertical platform capability — funeral home is the first implementation, but the infrastructure serves every vertical. Each vertical registers its domain-specific content types as plugins. 

## The Obituary Page as the Killer Feature 

Every competitor’s obituary page looks like it was built in 2012. Static photo, dates, a paragraph, a guestbook. None of them use AI. 

Bridgeable’s obituary page writes itself from the case file. The Scribe already captured the biography. The service details are already in `case_service` . The family information is in `case_informants` . When the case reaches the obituary step on the staircase, the page is already 80% complete. The director reviews and approves — they don’t write anything. 

This is the anchor feature. Families share obituary pages. Google indexes them. Every share and every search impression drives awareness of the funeral home’s Bridgeable-powered website. 

## Website → Funnel for Non-Bridgeable FHs 

A funeral home that joins just for the website is a lead, not a customer. They’re in the system, they have a relationship, and every login to update an obituary is an impression of the full platform. Gentle contextual nudges at the right moments (“You’ve added 10 obituaries manually — the AI Arrangement Scribe would write these automatically”) convert website-only customers over time without being annoying. 

Manual obituary entry is therefore a deliberate first-class path, not just a fallback. It means: 

- New FH tenants have a live site with real content from day one 

- FHs not yet using Bridgeable for case management can still have a world-class website 

- The “empty website” problem that kills onboarding momentum is eliminated 

## Architecture: Static Site Generation + Bridgeable API 

## Chosen approach: Static site generation deployed to Cloudflare Pages 

When a tenant publishes their site, Bridgeable generates static HTML/CSS/JS and deploys to Cloudflare Pages. Dynamic features (contact forms, live obituary updates, plot map) call back to the Bridgeable API at runtime. 

## Why not hosted dynamic pages: 

Static sites are faster, cheaper, and essentially unhackable 

- Cloudflare Pages is free at virtually any scale 

- Bridgeable API is already the source of truth — static pages just query it 

- Each tenant’s site is isolated — one tenant’s traffic or issue can’t affect another’s 

## Deployment flow: 

1. Tenant edits site in Bridgeable website builder UI 

2. Clicks “Publish” 

3. Bridgeable generates static site files 

4. Deploys to Cloudflare Pages via API 

5. Custom domain resolves automatically 

## Custom Domain Support — Two Paths 

## Self-serve path: 

- Tenant provides their domain in settings 

- Bridgeable shows exact DNS record to add (CNAME to Cloudflare Pages) 

- Bridgeable polls for verification automatically 

Goes live when DNS propagates 

## Managed path: 

- Tenant provides registrar login or transfers to Cloudflare (recommended — cheapest atcost registrar) 

- Bridgeable handles DNS via Cloudflare API — fully automated 

- One-click setup if tenant uses Cloudflare as registrar 

- Small fee or included in higher tier 

Cloudflare is the recommended registrar for all tenants — at-cost pricing, best DNS performance, and Bridgeable’s Cloudflare integration makes domain management fully programmable. 

## Bidirectional Data Flow 

This is what separates a Bridgeable website from Squarespace. It’s not a brochure — it’s a connected node in the tenant’s operational system. 

## Bridgeable → Website (auto-populated): 

- Case file → obituary page (biography, service details, family info, photo) 

- Service schedule → public service details page 

- Cemetery plot map → embeddable availability widget on cemetery site 

- GPL price list → FTC-required pricing page (auto-updated when prices change) 

- Staff profiles → about page 

Products/catalog → services and merchandise pages 

## Website → Bridgeable (data capture): 

- Contact form → CRM lead created automatically 

- Preneed inquiry → preneed lead in case pipeline 

- Flower order → logged against case 

- Family RSVP for service → attendance tracking in case 

- Plot inquiry from cemetery map → cemetery CRM lead 

- Online arrangement start → draft case created 

## GPL Pricing Page — FTC Compliance Built In 

The FTC Funeral Rule requires funeral homes to make their General Price List available. Some states now require it on the website. Bridgeable already has `price_list_versions` and `FTCComplianceService` built. 

The public pricing page is just a read-only view of the active GPL version — auto-updated every time the director updates prices in Bridgeable. No separate maintenance. Always current. Always compliant. Competitors charge extra for this. Bridgeable gets it for free because the data already exists. 

## Cross-Vertical Content Type Registry 

Universal website layer built once. Each vertical registers domain-specific content types: 

|Vertical|Domain Content Types|
|---|---|
|Funeral home|Obituary pages, service schedule, GPL pricing page, preneed inquiry|
|Cemetery|Interactive plot map, interment records, section/history pages|
|Manufacturer|Product catalog, dealer/FH locator map|
|||



|||
|---|---|
|Crematory|Services page, process information|
|Trucking|Service area map, load board|
|Contractor|Project portfolio, service area|



The cemetery plot map is worth noting specifically — the same interactive map built for the arrangement conference cross-tenant feature is embeddable on the cemetery’s public website. Families browse available plots before calling. No competitor has this. 

## Universal Page Types (All Verticals) 

Home page (hero, services summary, CTA) 

- About / Staff profiles 

- Services / Products 

- Contact (routes to CRM) 

- Custom pages (free-form content) 

- Blog / News 

## Template System 

Each vertical gets purpose-built templates designed for their industry. Not generic “business website” templates — layouts designed around how families actually use funeral home sites, how cemetery visitors browse, etc. 

- v1 ships with 2-3 templates per vertical. Templates are: 

   - Mobile-first responsive 

Pre-wired for all domain content types 

- Accessible (WCAG AA — matters for grieving families) 

- Fast (Lighthouse 90+ out of the box) 

## Flower Ordering Integration 

Standard funeral home website feature. Two approaches: 

- Affiliate link: Link out to FTD/Teleflora with UTM tracking. Zero integration work, small referral revenue. 

Embedded widget: FTD and Teleflora both have embeddable widgets. Drop in during 

website setup. 

FTD and Teleflora have funeral home affiliate programs specifically. This is a day-one feature that takes 30 minutes to configure per tenant — just affiliate account setup and widget embed code. 

## Livestreaming Integration 

Standard feature among competitors. Simplest path: 

- Embed a Zoom, YouTube Live, or Vimeo livestream URL on the service page 

- Director adds the stream URL when scheduling the service in Bridgeable 

- Auto-appears on the public service page at the right time 

No custom streaming infrastructure needed 

Purpose-built streaming (like some competitors offer) is a Phase 2 consideration if tenants want it. 

## Onboarding Flow (Setup-with-Support Model) 

v1 is setup-with-support, not fully self-serve. Bridgeable staff (or eventually a guided wizard) walks the FH through: 

1. Choose template 

2. Upload logo, set brand colors 

3. Configure pages (which pages to show, custom content) 

4. Connect domain (self-serve or managed) 

5. Add staff profiles 

6. Set up flower ordering affiliate 

7. Configure GPL pricing page (auto-pulls from Bridgeable if they have pricing set up) 

## 8. Publish 

Estimated setup time: 1-2 hours with support. Moves to self-serve wizard once the pattern is proven. 

## Onboarding Website Migration — Full Site Scrape 

When a FH provides their existing website URL during onboarding, Bridgeable runs a comprehensive Playwright scrape in one pass. The scraper is already on the site — might as 

well extract everything useful, not just obituaries. 

## What Gets Scraped 

## Obituaries (primary) 

- Full name, birth/death dates, photo, obituary text, service details, family survivors 

- Guestbook/tribute comments — first-class data objects, not discarded 

- Maps to: `funeral_cases` (source: “migrated_web”), `case_deceased` , `case_service` 

- Guestbook entries stored as `funeral_case_notes` with `note_type: "family_tribute"` 

- Claude normalizes formatting during import, optionally enhances sparse obituaries 

- Optional: “This obituary is very brief — would you like Claude to expand it?” 

## Staff / Team Pages 

- Names, titles, photos, bios of all funeral directors and staff 

- Pre-populates Bridgeable user account profiles and new website staff page 

- Name matching against historical cases can pre-associate director_id on migrated records 

## Services / Pricing 

- Current service offerings and any published pricing 

- If GPL is on site (increasingly required): Claude parses it → pre-populates `price_list_versions` 

Even informal services page seeds the onboarding checklist with what to configure 

## About / History 

- Founding year, ownership, community ties, mission statement 

- Feeds new website About page 

- Stored as tenant context — improves AI-generated obituary quality (“family-owned since 1952, serving the Catholic community in Rochester”) 

## Cemetery / Crematory Partners 

- Funeral homes typically list preferred partners 

- Pre-populates preferred partners list in Bridgeable 

- If any are on the Bridgeable network → connection suggested automatically during onboarding 

This is a cross-tenant network discovery mechanism built into onboarding 

## Contact Information 

- Address, phone, hours, after-hours number 

- Seeds tenant profile, GPL required fields, new website contact page 

## Testimonials / Reviews 

- Seeds new website social proof section immediately 

- Google rating/review count if linked from their site (reading their own published data, not scraping Google) 

## Pre-need / Planning Resources 

- Any forms or guides currently offered 

- Signals what their preneed workflow looks like before configuring that module 

## Platform Detection 

- Identifies current platform from page source, meta tags, footer credits 

- FrontRunner, Tribute Technology, Batesville WebLink, WordPress, etc. 

- Tells you: which competitor they’re leaving, what markup to expect, whether deeper export paths exist 

- Each platform gets a specialized obituary parser tuned to its markup 

## The Onboarding Intelligence Brief 

All scraped data feeds a Claude analysis pass that produces a structured brief before the setup call: 

```
Onboarding Brief — Riverside Funeral Home
```

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Founded: 1962, family-owned (3rd generation)
Current platform: FrontRunner Professional
Staff found: 4 funeral directors, 2 support staff
Obituaries found: 1,247 (earliest: 1987)
```

```
Services: burial, cremation, pre-need, veterans
Current GPL: found — 34 line items extracted
Pricing last updated: estimated 2023
```

```
Preferred cemetery partners: 3 found
```

```
  → St. Mary's Cemetery is on Bridgeable network ✓
```

- `→ Lakeview Memorial: not on network` 

```
  → Pinecrest: not on network
Preferred crematory: Valley Cremation (not on network)
Pre-need: forms found — appears to use paper process
Testimonials: 47 extracted
Social: Facebook active, Google Business linked
```

```
Suggested onboarding priorities:
```

`1. Review extracted GPL — 34 items ready to import` 

`2. Create accounts for 4 directors (names + photos ready)` 

`3. St. Mary's network connection available — suggest enabling` 

`4. Pre-need module: manual process detected, strong upgrade candidate` 

`5. 1,247 obituaries queued for background migration` 

This brief becomes the foundation for the setup-with-support call. Instead of asking a hundred questions, Bridgeable already knows the operation. The conversation is “here’s what we found — does this look right?” not “tell us about yourself.” 

## Migration Data Model Additions 

Add to `funeral_cases` : 

```
source: Mapped[str]
# "bridgeable" | "migrated_web" | "migrated_csv" | "manual"
migration_source_url: Mapped[Optional[str]]    # Original obituary URL
migration_source_platform: Mapped[Optional[str]]  # frontrunner | tribute | bates
migration_imported_at: Mapped[Optional[datetime]]
```

Migrated historical cases are read-only by default — they populate the public website but don’t appear in the active case workflow. Director can optionally “activate” a case if needed (e.g., a preneed originally on the old site). 

## Scraper Architecture 

- Playwright crawl with 1.5s polite delay between pages (same pattern as Wilbert catalog scraper) 

- Runs as background job — director continues onboarding while it runs 

- Progress indicator: “Migrating your history… 847 of 1,247 obituaries complete” 

- Per-platform parser registry — each known platform has a specialized extractor 

Falls back to Claude vision/HTML analysis for unknown platforms 

Rate limited to avoid overwhelming small funeral home hosting 

## Competitive Significance 

No competitor offers history migration. Switching from FrontRunner or Batesville WebLink to any other platform means losing years of obituary history — a real emotional and practical switching cost that keeps funeral homes captive. 

Bridgeable eliminates that switching cost entirely. The pitch: “Switch to Bridgeable and bring your entire history with you.” This unlocks a market segment that has been held captive by incumbents purely because migration pain was too high. 

## Brand Extraction and Tasteful Modernization 

Rather than asking a funeral director to make a hundred design decisions, Bridgeable extracts their existing brand during the site scrape and applies conservative modernization automatically. The pitch: “We kept everything that makes your brand yours and cleaned it up a little.” 

This is a much easier onboarding sell than “pick a template.” The director recognizes their site. It just looks better. 

## What Gets Extracted 

Colors are almost always in CSS — primary, secondary, accent, background, text. Logo is in the header. Fonts are in CSS font-family declarations — Google Fonts are identifiable by name. Layout preferences are inferred from page structure — do they lead with obituaries or services? Are they photo-heavy or text-forward? 

## What “Tasteful Modernization” Means for Funeral Homes 

The most common issues on existing FH sites are very fixable without changing brand identity: 

- Typography too small or using outdated web fonts — keep their font, fix sizing hierarchy and line height 

- Colors correct but applied inconsistently — standardize their palette across components 

- Photos low resolution or awkwardly cropped — same layout, better presentation 

- Navigation too cluttered — simplify without removing anything 

- Mobile layout broken — their desktop design adapted properly for mobile 

- Obituary pages that feel clinical — same information, warmer layout with better photo treatment 

None of these feel like a rebrand. They feel like their site got polished. 

## Claude Vision Analysis Pass 

After scraping CSS and taking key page screenshots, Claude vision analyzes: 

- Overall tone (formal/traditional vs. warm/contemporary) 

- Color harmony issues 

- Typography hierarchy problems 

- What’s working well and must be preserved exactly 

What looks dated and has a modern equivalent that feels similar 

## Modernization prompt to Claude: 

```
You are a tasteful web designer helping a funeral home modernize their website
without losing their brand identity. Funeral homes serve grieving families —
the design must remain dignified, warm, and trustworthy. No trendy design
choices. No dramatic departures from their existing look.
```

```
Here is their current homepage screenshot: [image]
Here is their current color palette: [colors]
Here are their current fonts: [fonts]
```

```
Provide specific, conservative modernization suggestions:
```

`1. Typography adjustments (sizing, line height, hierarchy only — keep their font)` 

`2. Color refinements (harmonize their existing palette — do not rebrand)` 

`3. Spacing and whitespace improvements` 

`4. Mobile layout recommendations` 

`5. What is working well and should be preserved exactly as-is` 

```
Do not suggest: new colors outside their palette, font changes unless the
current font is unavailable as a web font, layout changes that alter the
fundamental character of the site.
```

- `Output as JSON: { "preserve_exactly": [],` 

- `"typography_adjustments": [],` 

- `"color_refinements": {},` 

- `"spacing_notes": [],` 

- `"mobile_notes": [],` 

```
  "overall_assessment": ""
```

```
}
```

## **`tenant_brand_extractions`** Table 

## New table created during onboarding scrape: 

```
class TenantBrandExtraction(Base):
```

```
    __tablename__ = "tenant_brand_extractions"
```

```
    id: Mapped[str]
```

```
    company_id: Mapped[str]            # FK to companies
```

## `# Colors extracted from CSS` 

```
    primary_color: Mapped[Optional[str]]       # Hex
    secondary_color: Mapped[Optional[str]]
    accent_color: Mapped[Optional[str]]
    background_color: Mapped[Optional[str]]
    text_color: Mapped[Optional[str]]
    raw_color_palette: Mapped[Optional[list]]   # All colors found, JSONB
```

## `# Typography` 

```
    heading_font: Mapped[Optional[str]]
    body_font: Mapped[Optional[str]]
    font_source: Mapped[Optional[str]]          # google | system | custom
```

```
    # Logo
```

```
    logo_url: Mapped[Optional[str]]
    logo_r2_key: Mapped[Optional[str]]          # Downloaded and stored in R2
    # Layout preferences inferred
    layout_style: Mapped[Optional[str]]         # traditional | contemporary | mi
    leads_with: Mapped[Optional[str]]           # obituaries | services | about
    photo_heavy: Mapped[Optional[bool]]
    current_platform: Mapped[Optional[str]]     # frontrunner | tribute | batesvi
```

## `# Claude analysis output` 

```
    tone_assessment: Mapped[Optional[str]]
    modernization_suggestions: Mapped[Optional[dict]]  # JSONB — full Claude outp
    preservation_notes: Mapped[Optional[str]]   # What must be kept exactly
```

```
    # Screenshots for reference
```

```
    homepage_screenshot_r2_key: Mapped[Optional[str]]
```

```
    extracted_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
```

## Director-Facing Onboarding Experience 

After scrape completes, director sees a side-by-side preview: 

```
YOUR CURRENT SITE          YOUR BRIDGEABLE SITE
```

```
[screenshot]               [live preview]
```

```
What we kept:              What we improved:
```

```
✓ Your navy & gold colors  • Typography cleaned up
```

```
✓ Your logo                • Mobile layout fixed
```

```
✓ Your serif headings      • Colors harmonized
```

- `✓ Your obituary-first      • Photo treatment layout                     modernized` 

Two buttons: 

“Looks good — use this design” → site published with extracted + modernized brand 

- “Let me adjust something” → opens constrained brand settings panel 

Most directors click “looks good” because the hard decisions were already made for them. 

## The Constrained Brand Settings Panel 

The adjustment panel is deliberately limited. This is a feature, not a limitation — it means every Bridgeable funeral home website looks professionally appropriate regardless of what the director chooses. 

## What can be adjusted: 

Colors: only from their extracted palette plus white and black 

- Fonts: curated list of 8-10 appropriate typefaces (no Comic Sans moments) 

- Layout: 3 options that all feel appropriate for the industry 

- Logo: upload replacement 

## What cannot be adjusted: 

Colors outside their extracted palette (prevents accidental rebranding) 

- Fonts that don’t suit the death care industry 

- Layout styles inappropriate for funeral homes 

The platform has taste built in. The constraint palette changes per vertical — funeral homes 

get dignified/muted options, contractors get bold/professional, etc. 

## Cross-Vertical Application 

The same scrape-and-modernize approach works for every vertical. A contractor’s site gets identical treatment — extract brand, modernize conservatively, preserve identity. The aesthetic constraint range just adjusts per vertical during the Claude analysis prompt. 

This means the website builder onboarding is essentially the same flow for every vertical — provide your URL, we handle the rest. 

## Open Items for Brand Extraction 

- CSS color extraction logic — handle CSS variables, computed styles, inline styles 

- Google Fonts detection and availability verification 

- Logo extraction — handle SVG, PNG, WebP, various header patterns 

- Screenshot capture via Playwright — full page vs. viewport, mobile vs. desktop 

- Per-vertical font curation list (8-10 fonts per vertical, pre-approved) 

- Per-vertical aesthetic constraint definitions for Claude prompt 

- Side-by-side preview component in onboarding UI 

- Brand settings panel — constrained adjustment UX design 

## Open Items for Website Builder 

- Cloudflare Pages API integration research — programmatic deployment flow 

- Static site generator choice — Next.js static export vs. Astro vs. custom 

- Template design for funeral home vertical (needs designer involvement) 

- FTD/Teleflora affiliate program signup and widget documentation 

- Domain management UI design — self-serve DNS verification flow 

- Livestream URL integration with case_service.service_date scheduling 

- GPL pricing page design — FTC-compliant layout 

- Cemetery plot map embed API design (serves both arrangement conference and public site) 

- Per-platform obituary parser research — FrontRunner, Tribute Technology, Batesville 

WebLink markup patterns 

- Guestbook/tribute comment data model — first-class object, not just notes 

- Background migration job architecture — progress tracking, error handling, resume on failure 

- Onboarding intelligence brief design — Claude prompt + output format 

- Partner network discovery flow — cemetery/crematory match during scrape → suggest connection 

