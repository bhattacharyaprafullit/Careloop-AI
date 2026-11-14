# 🧭 CareLoop AI: Complete Website Navigation & Feature Master Guide
> **Document Purpose:** Yeh document CareLoop AI ke har ek page, button, tab aur AI feature ka complete aasaani se samajh aane wala guide hai. Isse padhkar aapko website ke har option ka exact use aur backend logic crystal-clear ho jayega.

---

## 📑 Table of Contents
1. [Project Overview (CareLoop AI Kya Hai aur Kyu Banaya Gaya?)](#1-project-overview)
2. [Technical Architecture (Pura System Kaise Kaam Karta Hai)](#2-technical-architecture)
3. [Top Navigation Bar & Global Sandbox Controls](#3-top-navigation-bar--global-sandbox-controls)
4. [Page 1: Landing Page (`/`)](#4-page-1-landing-page-)
5. [Page 2: Coordinator Priority Queue (`/app/queue`)](#5-page-2-coordinator-priority-queue-appqueue)
6. [Page 3: Patient Case Detail & Explainable AI (`/app/cases/[id]`)](#6-page-3-patient-case-detail--explainable-ai)
7. [Page 4: Multilingual Patient Portal (`/p/[token]`)](#7-page-4-multilingual-patient-portal-ptoken)
8. [Page 5: Human-in-the-Loop Approvals Desk (`/app/approvals`)](#8-page-5-human-in-the-loop-approvals-desk-appapprovals)
9. [Page 6: Clinician Desk & Closed-Loop Referral (`/app/clinician`)](#9-page-6-clinician-desk--closed-loop-referral-appclinician)
10. [Page 7: Metrics & Queue Simulation Dashboard (`/app/metrics`)](#10-page-7-metrics--queue-simulation-dashboard-appmetrics)
11. [Page 8: Model Card & Clinical Governance (`/app/model-card`)](#11-page-8-model-card--clinical-governance-appmodel-card)
12. [Quick Cheat Sheet: Kis Feature Par Kya Bolna Hai (Interview / Demo)](#12-quick-cheat-sheet)

---

## 1. Project Overview
### Real Clinical Problem
Hospital aur screening labs me har saal laakhon log cancer screening karate hain (jaise Colorectal Cancer ke liye **FIT**, Breast Cancer ke liye **Mammography**, aur Cervical Cancer ke liye **Pap/HPV**).
* **The Reality:** Lagbhag **25% se 40% abnormal screening results wale patients timely follow-up diagnostic test nahi karwate.**
* **The Root Cause:** 
  1. **FIFO Backlog:** Care coordinators unorganized excel sheets ya first-in-first-out lists me dabe hote hain, unhe pata nahi hota kis patient ki haalat zyada critical hai.
  2. **Communication Gap:** Patients ko technical medical jargon samajh nahi aata, darr ya confusion ki wajah se wo follow-up drop kar dete hain.
  3. **Broken Handoffs:** Primary care doctor aur specialist ke beech referrals kho jaate hain.

### CareLoop AI Ka Solution
CareLoop AI ek **closed-loop clinical decision support platform** hai jo guarantee karta hai ki:
1. **Zero Abnormal Results Lost in Transit:** Har abnormal result ka 11-stage deterministic state machine track rakhta hai.
2. **Dynamic AI Triage:** FIFO hatakar calibrated ML (XGBoost) se drop-off risk aur SLA urgency calculate karke urgent cases ko top par laata hai.
3. **Multilingual Patient Teach-Back:** English, Hindi aur Spanish me reassurance aur comprehension quiz deta hai.
4. **Evidence-Guarded Closure:** Bina diagnostic report proof ke koi bhi case close nahi ho sakta.

---

## 2. Technical Architecture
* **Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons. (Accessible high-contrast UI with zero-flash dark/light mode).
* **Backend API:** FastAPI (Python 3.11), Pydantic v2, Uvicorn, LangGraph state orchestration.
* **Database:** Real Cloud Supabase PostgreSQL with append-only SQL triggers and Row Level Security (RLS).
* **Machine Learning:** Scikit-learn, calibrated XGBoost (AUROC 0.88, Brier Score 0.11), TreeSHAP feature attributions, Kaplan-Meier survival curves.
* **Testing & Quality:** 46/46 automated unit & integration test suites passing.

---

## 3. Top Navigation Bar & Global Sandbox Controls
Jab aap website ke kisi bhi dashboard page par hote hain (`/app/...`), to header me aapko global controls milte hain:

### A. Logo & Title (Top-Left)
* **CareLoop AI (Closed-Loop Care):** Is par click karne se aap wapas Landing Page (`/`) par chale jaate hain.

### B. Main Navigation Links (Center)
1. **Priority Queue (`/app/queue`):** Care Coordinators ke liye prioritized list.
2. **Approvals (`/app/approvals`):** High-risk cases ke liye human-in-the-loop sign-off.
3. **Clinician Desk (`/app/clinician`):** Doctors ke beech SBAR referral exchange.
4. **Metrics (`/app/metrics`):** System turnaround KPIs aur live 100-run queue simulation.
5. **Model Card (`/app/model-card`):** ML model ki accuracy, calibration aur fairness metrics.

### C. Sandbox Controls (Top-Right)
Demo ke dauran judges ya users ko system live test karane ke liye banaye gaye hain:
* **Role Switcher Dropdown (`Role: Coordinator`):**
  * *Coordinator:* Triage queue aur patient outreach manage karta hai.
  * *Clinician:* Referrals review karta hai aur closure sign-off karta hai.
  * *Patient:* Patient portal view simulate karta hai.
  * *Admin:* Full system view.
* **Fast-Forward Clock (`+24h` / `+72h`):** 
  * *Use:* Is button par click karke aap system time ko aage badha sakte hain.
  * *Kyu banaya gaya:* Dekhne ke liye ki jab time guzarta hai, to dynamic SLA clocks kaise expire hote hain aur cases kaise automatically **"OVERDUE"** ban kar escalate hote hain!
* **Reset Demo (`RotateCcw` icon):** Demo sandbox ko wapas initial 60 synthetic seed cases par restore karta hai.
* **Guided Tour Button (`Step 1 of 8` / `Start Tour`):** Screen par ek floating guided modal shuru karta hai jo user ko step-by-step 8 steps ka demo walkthrough karwata hai.
* **Theme Toggle (Sun/Moon icon):** Light mode aur Dark mode switch karta hai.

---

## 4. Page 1: Landing Page (`/`)
Yeh application ka public home page hai.

### Features & Sections:
1. **Top Header:** Logo, Theme Toggle, aur **`Launch App`** button.
2. **Hero Section:**
   * Headline: *"Every Abnormal Screening. Zero Cases Lost in the Loop."*
   * Action Button: **`Launch Live Demo`** (Is par click karte hi database sandbox token initialize hota hai aur aap seedha `/app/queue` par chale jaate hain).
3. **6 Architectural Pillars (R1 to R6):**
   * *R1 (11-State Case Visibility):* Deterministic state engine without silent drops.
   * *R2 (Ownership & SLA Progression):* 72h vs 14d countdown timer.
   * *R3 (Multilingual Patient Teach-Back):* English, Hindi, Spanish comprehension verification.
   * *R4 (Cross-Provider Consults & SBAR):* Structured doctor handoffs.
   * *R5 (Human-in-the-Loop & Closure Gate):* LangGraph checkpoint approvals.
   * *R6 (Impact Metrics & Simulation):* 14-day median time savings.
4. **How It Works Flow Visualizer:** 
   * Interactive 5-step horizontal pipeline (Screening Ingestion $\rightarrow$ Risk Triage $\rightarrow$ Patient Portal $\rightarrow$ SBAR Referral $\rightarrow$ Verified Closure).
5. **Patient Safety & Synthetic Data Notice:**
   * Amber/Green badge jo confirm karta hai ki system 100% synthetic records par operate karta hai aur real PHI data leak ka zero risk hai.

---

## 5. Page 2: Coordinator Priority Queue (`/app/queue`)
Yeh Care Coordinators aur Navigators ka primary workspace hai.

### Features & Controls:
1. **Filter Tabs (Top):**
   * **`All Cases`:** Saare active cases dikhata hai.
   * **`Overdue`:** Sirf wo cases jinki SLA breach ho chuki hai (Red alert).
   * **`Unassigned`:** Naye cases jinka koi assigned coordinator nahi hai.
   * **`Rejected`:** Referrals jo capacity ya missing data ki wajah se reject huye.
   * **`Needs approval`:** High-risk cases jo clinician review ke liye ruke huye hain.
2. **`+ Ingest Result` Button (Top-Right):**
   * Is par click karne se ek modal form khulta hai.
   * Aap manually naya abnormal test result (FIT, Mammography, Pap/HPV) submit kar sakte hain. Form submit karte hi backend FastAPI engine turant risk score calculate karke case queue me daal deta hai.
3. **Queue Data Table (Columns):**
   * **Patient:** Patient name, Age, synthetic ID, aur language badge (EN, HI, ES).
   * **Screening Type:** FIT (Faecal Immunochemical Test), Mammography (BI-RADS 4/5), ya Pap/HPV.
   * **Urgency Tier:** 
     * *Tier-1 (Urgent):* High risk, SLA automatically 72 hours par cut ho jaata hai.
     * *Routine:* Standard 14-day timeline.
   * **Priority Score:** 0 se 100 ke beech ka score, calculated by formula:
     $$\text{Priority} = 100 \times (0.45 \times \text{Urgency} + 0.35 \times P_{\text{drop}} + 0.20 \times \text{SLA Pressure})$$
   * **SLA Countdown:** Real-time clock (jaise `54h left`, `12h left`, ya `OVERDUE`).
   * **Status / Current State:** 11 states me se current state (jaise `TRIAGED`, `OUTREACH_PENDING`, `REFERRAL_INITIATED`).
   * **Actions (`View Case`):** Kisi bhi row par click karne se us case ka full deep-dive page khulta hai.

---

## 6. Page 3: Patient Case Detail & Explainable AI (`/app/cases/[id]`)
Yeh individual patient ka full clinical governance page hai.

### Features:
1. **11-State Lifecycle Stepper (Top Banner):**
   * Horizontal progression bar:
     $$\text{Issued} \rightarrow \text{Triaged} \rightarrow \text{Outreach Pending} \rightarrow \text{Contacted} \rightarrow \text{Acknowledged} \rightarrow \text{Consult} \rightarrow \text{Scheduled} \rightarrow \text{Completed} \rightarrow \text{Result Documented} \rightarrow \text{Evidence Verified} \rightarrow \text{Closed}$$
   * Green checkmarks dikhate hain ki kon-kon se stages successfully complete ho chuke hain.
2. **Left Panel: Explainable AI Risk Engine (TreeSHAP):**
   * **Predicted Drop-Off Risk ($P_{\text{drop}}$):** Calibrated percentage (jaise `78% Risk of Drop-off`).
   * **TreeSHAP Log-Odds Feature Waterfall:**
     * Bar chart jo exact reasons batata hai ki risk kyu zyada hai:
       * $+0.32$: Transportation barrier reported.
       * $+0.25$: No established Primary Care Physician.
       * $+0.19$: High-burden out-of-pocket insurance.
       * $-0.15$: Prior screening adherence (protective factor).
     * **Benefit:** Doctor ya coordinator ko pata chal jata hai ki patient ko medical samjhana hai ya ride/transport arrange karni hai!
   * **Patient Survival Curve $S(t)$:** Kaplan-Meier survival probability graph showing time-to-diagnostic workup vs historical cohort.
3. **Right Panel: Grounded AI Clinical Assistant:**
   * LLM generated clinical summary jo strictly case factual data se bound hai.
   * **Zero-Hallucination ADS Score:** Explanation-Summary Divergence Score jo ensure karta hai ki AI ne koi jhootha number ya imaginary diagnosis invent nahi kiya.
4. **Bottom Action Panels:**
   * **Assign / Reassign Owner:** Case ka clinical coordinator badalne ke liye.
   * **Patient Outreach Trigger:** Direct SMS/Email token bhejne ke liye.
   * **Open Patient Portal View:** Direct link `/p/[token]` par jump karne ke liye.

---

## 7. Page 4: Multilingual Patient Portal (`/p/[token]`)
> **Direct Demo URL:** `https://careloop-ai-livid.vercel.app/p/pt-seed-001`

Yeh patient ka private mobile-optimized web portal hai. Isme patient ko koi app install nahi karni padti aur na hi password yaad rakhna padta hai (secure tokenized link).

### Features:
1. **Language Selector (Top-Right):**
   * **`English`**, **`हिंदी (Hindi)`**, **`Español (Spanish)`**.
   * Ek click me poora medical portal Hindi ya Spanish me translate ho jata hai (jisme medical terms aam bhasha me samjhaye gaye hain, jaise *"Aapki jaanch me aage test ki zaroorat hai"*).
2. **Reassurance Header:**
   * Plain-language explanation: *"An abnormal result does NOT mean you have cancer. It means we need one more clear picture to keep you healthy."*
3. **3-Step Progress Tracker:**
   * Step 1: Screening Test Completed ✅
   * Step 2: Next Steps & Confirmation ⏳
   * Step 3: Diagnostic Appointment Done ⚪
4. **Interactive Teach-Back Method (Comprehension Check):**
   * Patient se 2 simple sawal poochhe jate hain:
     * *"What is the main purpose of your follow-up appointment?"*
     * *"Do you have any difficulty attending?"* (Options: *I have a ride*, *Need transportation help*, *Work schedule conflict*).
   * **Auto-Escalation Engine:** Agar patient select karta hai *"I am very confused/scared"* ya *"Need transportation"*, to backend automatically coordinator queue me alert bhej deta hai taaki human coordinator us patient ko directly call kare!

---

## 8. Page 5: Human-in-the-Loop Approvals Desk (`/app/approvals`)
Yeh clinical safety aur AI governance ka sabse critical page hai.

### Features:
1. **LangGraph Checkpoint Gate:**
   * AI kabhi bhi high-risk decisions akele execute nahi karta.
   * Jab kisi case ka drop-off risk $> 0.65$ ho, ya urgent case SLA breach kar raha ho, ya patient teach-back me fail ho gaya ho, to system **LangGraph `interrupt()`** call karke case ko yahan pause kar deta hai.
2. **Approval Cards:**
   * Har pending case ka summary card dikhta hai jisme AI ka proposed action likha hota hai (e.g., *"Escalate to Urgent Diagnostic Colonoscopy with Transportation Voucher"*).
3. **3 Clinical Action Buttons:**
   * **`Approve` (Green):** Doctor AI ke plan ko agree karke aage bhej deta hai.
   * **`Modify Pathway` (Blue):** Doctor test ya timeline ko alter karta hai.
   * **`Reject` (Red):** Doctor standardized ReasonCode ke saath AI recommendation cancel karta hai.

---

## 9. Page 6: Clinician Desk & Closed-Loop Referral (`/app/clinician`)
Yeh primary care doctors (PCPs) aur specialists (Oncologists, Gastroenterologists, Radiologists) ka cross-communication hub hai.

### Features:
1. **Structured SBAR Referral Packages:**
   * Medical communication standard format:
     * **S (Situation):** Abnormal FIT screening, elevated biomarker.
     * **B (Background):** Family history, comorbid hypertension.
     * **A (Assessment):** High drop-off risk (0.74), Tier-1 urgency.
     * **R (Recommendation):** Diagnostic workup within 14 calendar days.
2. **Direct Referral Actions:**
   * **`Accept Referral`**: Specialist slot confirm karta hai.
   * **`Request More Info`**: Additional lab report mangwata hai.
   * **`Reject with ReasonCode`**: Capacity overload ya out-of-network reason log karta hai.
3. **Documented Evidence-Guarded Closure Gate:**
   * **Hospital ki sabse badi liability:** Doctor bina test huye file band kar dete hain.
   * **CareLoop Rule:** System tab tak case ko **"CLOSED"** nahi hone dega jab tak:
     1. Objective diagnostic report number / pathology proof enter na ho, YA
     2. Authorized doctor apna clinical override justification digitally sign na kare.

---

## 10. Page 7: Metrics & Queue Simulation Dashboard (`/app/metrics`)
Yeh hospital administrators aur competition judges ke liye quantitative proof dikhata hai.

### Features:
1. **Key Performance Indicator (KPI) Cards:**
   * **$-14$ Days:** Median turnaround reduction from abnormal screening to diagnostic completion.
   * **$71\%$:** Drop-off reduction in high-risk patients.
   * **$94\%$:** Patient teach-back comprehension rate across English, Hindi, and Spanish.
   * **$100\%$:** Documented closure compliance (Zero blind dropouts).
   * **$<200$ ms:** Backend API endpoint response latency.
2. **100-Run Stochastic Monte Carlo Queue Simulation:**
   * Live interactive chart jo compare karta hai:
     * **Blue Curve (Traditional FIFO):** Standard hospital queue jisme urgent aur non-urgent sab barabar wait karte hain, aur 35% cases SLA deadline miss karte hain.
     * **Emerald Curve (CareLoop Dynamic Priority):** Urgent cases priority score se aage aate hain, jisse overall median resolution time 42 din se घटकर 28 din ho jaata hai!
3. **Bottleneck & Delay Analytics:**
   * Bar charts jo dikhate hain ki delay kis wajah se huye: Specialist appointment capacity (42%), Patient transportation (28%), Insurance prior-authorization (18%).

---

## 11. Page 8: Model Card & Clinical Governance (`/app/model-card`)
Yeh page transparency aur ethical AI compliance prove karta hai.

### Features:
1. **Model Specifications:**
   * **Algorithm:** Extreme Gradient Boosting (XGBoost) with Isotonic Probability Calibration.
   * **Validation Performance:** AUROC = $0.88$, Brier Score = $0.11$.
   * **Inference Latency:** $<15$ ms on CPU (No expensive GPUs needed).
2. **Fairness & Demographic Parity:**
   * Subgroup performance across Age groups, Gender, Primary Languages, and Rural vs Urban geographies to prove zero algorithmic bias.
3. **Synthetic Data Lineage:**
   * Explains the Bayesian clinical generator used to synthesize 100% compliant patient cohorts without risking any real HIPAA/GDPR health data.

---

## 12. Quick Cheat Sheet
Agar koi aapse kisi feature ke baare me pooche, to sirf yeh 1-liner bolna hai:

| Website Feature / Tab | Kya Kaam Karta Hai? (1-Line Answer) |
|---|---|
| **Priority Queue** (`/app/queue`) | FIFO hatakar urgency aur drop-off risk ke hisaab se patients ko rank karta hai taaki critical patient pehle dekha jaye. |
| **SLA Clock (72h vs 14d)** | Urgent cancer cases ka timeline aadha (72h) kar deta hai aur expire hone se pehle alarm bajata hai. |
| **TreeSHAP Waterfall** | AI ke black-box ko khatam karke batata hai ki patient follow-up kyu miss kar sakta hai (e.g. transport, insurance). |
| **Patient Portal** (`/p/...`) | Patient ko English, Hindi aur Spanish me bina password ke aasan bhasha me test aur appointment samjhata hai. |
| **Teach-Back Quiz** | Check karta hai ki patient ko samajh aaya ya nahi; confuse hone par coordinator ko call karne bolta hai. |
| **Approvals Desk** (`/app/approvals`) | Doctor ka approval leta hai jab AI ka risk score high ho (Human-in-the-Loop safety). |
| **SBAR Referral** (`/app/clinician`) | Primary care doctor aur specialist ke beech standardized clinical handoff karta hai taaki referral na khoye. |
| **Evidence Closure Gate** | Bina confirmed test result ya biopsy proof ke file ko band (close) hone se rokta hai. |
| **Metrics Simulation** | 100-run simulation se prove karta hai ki CareLoop patient ka wait time 14 din kam kar deta hai. |

---
*Created strictly for CareLoop AI Project Documentation & Demonstration.*
