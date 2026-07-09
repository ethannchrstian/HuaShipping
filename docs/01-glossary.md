# 01 — Glossary (Bahasa Indonesia ↔ English code names)

Convention for the whole project: **user-facing text is Bahasa Indonesia; code,
database fields, tests, and docs are English.** This table is the single mapping
between the two. When adding a model field or UI string, check here first and
extend this file if the term is new.

## Domain terms

| Indonesian (as used by the company) | English (code name) | Meaning / notes |
|---|---|---|
| voyage, voy. | `voyage` | One round trip of a vessel set; coded `V<yy><nn>` e.g. `V2601` |
| kapal | `vessel` | Here always a **tug + barge set**, e.g. TB. HUA Navigator 1 & BG. Palm Hero 2401 |
| TB (tug boat) | `tug` | The powered boat |
| BG (barge / tongkang) | `barge` | The cargo barge (carries the CPO) |
| jetty | `jetty` | Loading/discharge berth, usually owned by a palm-oil company |
| pelabuhan | `port` | Port/city a jetty belongs to (Dumai, Belitung, Palembang…) |
| muatan | `cargo` | The cargo, e.g. "CPO 4.000 MT" |
| CPO | `CPO` | Crude Palm Oil (main commodity) |
| MT | `metric_tons` | Tonnage unit; some old sheets use KG (1 MT = 1,000 KG) |
| muat | `load` / `loading` | Loading operation |
| bongkar | `discharge` | Discharging operation |
| lokasi muat / bongkar | `load_location` / `discharge_location` | Jetty where loading/discharge happens |
| kegiatan | `activity` | One timestamped entry in the time sheet |
| perjalanan ke lokasi muat | `ballast_voyage` | Sailing empty to the load port |
| perjalanan ke lokasi bongkar | `laden_voyage` | Sailing loaded to the discharge port |
| sandar | `berthing` | Coming alongside the jetty |
| tunggu info sandar | `waiting_berth` | Waiting for permission/instruction to berth |
| tunggu info muat / bongkar | `waiting_load` / `waiting_discharge` | Waiting at berth for cargo ops to start |
| cast off | `cast_off` | Leaving the berth; "tunggu info cast off" = `waiting_cast_off` |
| shifting | `shifting` | Moving between jetties within one port call |
| persiapan (ke lokasi muat) | `preparation` | Idle/prep time bridging to the next voyage |
| time sheet | `statement_of_facts` (industry term), `timesheet` informally | The per-voyage log of all activities |
| lama muat/bongkar | `laytime` | Contractual days allowed for load+discharge (may be split: "6 hari muat + 6 hari bongkar") |
| prorata muat–bongkar sesuai kontrak | `laytime_allowed` | Same as laytime, as printed in the totals block |
| demurrage | `demurrage` | Penalty payable by charterer when port time exceeds laytime; rate in Rp/hari |
| No. Kontrak | `contract_no` | Charter contract number, e.g. `001/FN-HUAT/I/2026` |
| kwitansi (nomor) | `invoice_no` | Invoice/receipt number, e.g. `001/INV/HUAT-FPS/I/2026` |
| pencharter | `charterer` | The customer chartering the vessel (FPS, PSCOI, PNLF, GGU, SIP…) |
| shipper | `shipper` | Cargo owner for a parcel (can differ from charterer on multi-parcel voyages) |
| freight | `freight` | Revenue for the voyage |
| bunker / BBM | `bunker` / `fuel` | Fuel; `bunker_price`, `fuel_used` |
| hari | `days` | Day counts; **always computed from timestamps, never typed** |
| berangkat / tiba | `departure` / `arrival` | From/to columns in the time sheet |
| tgl / pukul | `date` / `time` | Date / clock-time columns |
| Dibuat oleh / Diketahui oleh | `prepared_by` / `acknowledged_by` | Signature roles on the printed sheet |
| Operasional | `operations` (role) | Admin staff role that prepares time sheets (currently Felicia) |
| Direktur Utama | `director` (role) | Signs off; consumes recaps (currently Tjipta Lesmana Suwarto) |
| rekap | `recap` | Summary view/report of voyages |
| stevedoring / buruh bongkar muat | `stevedoring` | Cargo-handling labor at the jetty; a per-voyage cost category |
| biaya | `cost` | Voyage cost line items (`voyage_cost`): stevedoring, port charges, agen, bunker… |
| agen | `agency` | Port agency fees (cost category) |
| Rp / IDR | `IDR` | Indonesian Rupiah; store as **integer rupiah** |

## App terms (UI strings we will need in Indonesian)

| English (code) | Indonesian (UI) |
|---|---|
| Voyage list | Rekap voyage |
| Ongoing / Completed | Berjalan / Selesai |
| Add activity | Tambah kegiatan |
| Master data | Data master |
| Export | Ekspor (CSV/Excel) |
| Warning: gap in log | Peringatan: ada waktu tidak tercatat |
| Warning: end before start | Peringatan: waktu selesai sebelum waktu mulai |
| Locked | Terkunci |
| Sign in / out | Masuk / Keluar |
