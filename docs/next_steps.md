## First buyer should be independent imaging / radiology clinics
## RADIOLOGY!
## posture this as decision support, and not automation. It's just a tool that helps get the job done. Like a drill instead of a screwdriver. Still need an operator, but it will improve efficiency.

### Approximate scale (Utah Medicaid):
* Total CPT/HCPCS codes in system: 6,000–9,000
* Imaging-related CPT codes: ~300–600
* MRI-specific CPT codes: ~40–80
* Knee MRI–relevant CPTs: ~3–5

# Good Enough Prototype Goal
## CPTs to support in V1

### Handle exactly these three:
* 73721 — MRI knee without contrast
* 73722 — MRI knee with contrast
* 73723 — MRI knee with & without contrast

That’s it. Do not add more yet.

### Why this is perfect:
* Extremely common
* High denial rates
* Conservative therapy rules are strict
* Ordering clinics hate it
* Policy logic is repetitive → LLM-friendly

## What your system must do for each CPT

### You’re “done” when it can reliably:
#### Extract:
* Symptoms
* Duration
####Conservative therapy
* Red flags
#### Retrieve:
* CPT-specific criteria
#### Compare:
* Chart facts → policy requirements
Output:
* A clinician-readable checklist + gap report

## Stopping rule (important)

#### You are good enough to sell when:
* You can run 10 fake patient charts through your system and get consistent, structured reports that look like something a clinic would actually use.

## ✅ MUST HAVE (non-negotiable)
### 1️⃣ Product

#### Working API (or UI) that:
* Accepts chart text
* Returns structured report
* Deterministic-ish output (temperature low)

#### Clear explanation of:
* What it does
* What it does NOT do

### 2️⃣ Report format (this matters more than model choice)

#### Your output should look like this:

Example structure:
* Patient Summary (auto-extracted)
* CPT requested
* Medicaid criteria checklist
* Met
* Not met
* Missing info
* Suggested additions to chart
* Disclaimer (important)

### 3️⃣ Compliance basics (table stakes)
#### You should be able to confidently say:
* “We do not store PHI by default”
* “Data is processed in a HIPAA-compliant environment”
* “We can sign a BAA”

### 4️⃣ LLC
#### Why:
* Clinics won’t take individuals seriously
* BAAs require an entity
* Costs ~$100–$200
* Removes friction later
* This is worth doing before outreach.

### 5️⃣ One-page landing site
This does not need marketing polish.
#### It needs:
* What problem you solve
* Who it’s for
* One example screenshot (even fake)
* Contact email
* This builds legitimacy when they Google you after the call.

### 6️⃣ BAA template (not negotiated yet)

#### Have:
* A standard BAA template ready
* Reviewed lightly (even by ChatGPT + common sense)
* You don’t need a lawyer yet, but you need to show you’ve thought about it.

### Quick Checklist
#### Product
* Knee MRI CPTs supported (73721/22/23)
* 10+ mock patient charts tested
* Report output is stable
* Clear limitations documented

#### Compliance
* PHI handling story is consistent
* No unnecessary data storage
* BAA template exists
* Hosting environment is HIPAA-capable

#### Business
* LLC formed
* Business email (not Gmail ideally)
* Simple landing page live

#### Sales readiness
* 30-second explanation
* Demo flow rehearsed

### Cold Call Tips
#### Do not call radiology groups first.
#### Call:
* Orthopedic clinics
* Sports medicine clinics
* Primary care clinics that order MRIs
* They feel the pain before radiology does.
* Radiology cares later.