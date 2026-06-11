# 📘 PLAYBOOK — نظام مراقبة توفّر المنتجات + تنبيه تيليجرام

مرجع كامل للنظام اللي بنيناه (مثال: مراقبة مقاس M في تيشيرتات
[beyondfit-sa.com](https://beyondfit-sa.com))، وقالب جاهز لإعادة استخدامه لأي
موقع/منتج ثاني. مكتوب بالعربي مع المصطلحات التقنية بالإنجليزي.

> **آخر تحديث:** 2026-06-01 — المستودع: `Malkhwaiter/beyondfit-monitor` (public)

> ⚠️ **هذا المشروع تقاعد (2026-06-04)** — المهمة خلصت واشتُريت التيشيرتات.
> للسجل التشغيلي الكامل + دليل إحياء النمط لهدف جديد، شوف
> **[PROJECT_ARCHIVE.md](PROJECT_ARCHIVE.md)**.
> العلاقة: هذا الـ PLAYBOOK = المرجع المعماري الموسّع · الـ ARCHIVE = سجل المشروع
> المتقاعد + تفاصيل تشغيلية (أسرار، cron-job.org، أعطال runner) + خطوات الإحياء.

---

## جدول المحتويات
1. [نظرة عامة](#1-نظرة-عامة)
2. [المعمارية الكاملة](#2-المعمارية-الكاملة)
3. [آلية الجدولة (GitHub + cron-job.org)](#3-آلية-الجدولة)
4. [إعادة الاستخدام لموقع/منتج جديد — دليل خطوة بخطوة](#4-إعادة-الاستخدام--دليل-خطوة-بخطوة)
5. [حسب نوع الموقع: HTML ثابت مقابل JavaScript](#5-حسب-نوع-الموقع)
6. [استكشاف الأخطاء (Troubleshooting)](#6-استكشاف-الأخطاء)
7. [نقاط الأمان (Security)](#7-نقاط-الأمان)

---

## 1) نظرة عامة

النظام **bot يراقب صفحات منتجات** كل فترة، ويسوي ٣ أشياء:

| الوظيفة | الوصف |
|---------|-------|
| 🔔 **تنبيه فوري (instant alert)** | أول ما يتحوّل المقاس المطلوب من **نافد → متوفّر**، يرسل رسالة تيليجرام فوراً. ينبّه **مرة واحدة** عند كل تحوّل (ما يكرّر طول ما المقاس متوفّر). |
| 📋 **ملخص دوري (periodic summary)** | كل ٣ ساعات (بتوقيت دقيق عبر cron-job.org)، يرسل رسالة فيها: وقت الفحص بتوقيت السعودية + حالة المقاس لكل منتج + أي توفّر جديد. يُرسل **دائماً** حتى لو ما فيه جديد (رسالة اطمئنان). |
| 🗂️ **تتبّع الحالة (state tracking)** | يحفظ آخر حالة معروفة في ملف JSON داخل المستودع، عشان يعرف وش "جديد" ويمنع تكرار التنبيهات. |

**المبدأ الأساسي:** يقرأ بيانات التوفّر من الصفحة → يقارنها بالحالة المحفوظة →
ينبّه عند التحوّل → يحدّث الحالة. كل هذا يشتغل على **GitHub Actions مجاناً**
(لأن المستودع public = دقائق غير محدودة)، بدون أي سيرفر أو جهاز شغّال.

---

## 2) المعمارية الكاملة

### بنية المشروع
```
beyondfit-monitor/
├── monitor.py                  # كل المنطق (fetch, parse, notify, state, summary)
├── products.json               # الإعدادات: قائمة المنتجات + المقاسات المراقَبة
├── requirements.txt            # requests
├── state/
│   ├── known_stock.json        # الحالة المحفوظة (يحدّثها البوت ويكوميتها)
│   └── summary_state.json       # آخر وقت أُرسل فيه ملخص (للـ fallback الزمني)
├── .github/workflows/
│   └── monitor.yml             # الجدولة + بيئة التشغيل + كوميت الحالة
└── PLAYBOOK.md                 # هذا الملف
```

### `monitor.py` — الدوال الرئيسية

#### `collect_product(url)` — القراءة والكشف
- يجيب صفحة المنتج عبر `requests.get` (HTML ثابت، **بدون JavaScript**).
- يستخرج بيانات المقاسات من العنصر `<salla-product-options options="...">`
  (JSON مُرمّز داخل الـ HTML).
- لكل مقاس فيه علم `is_out`: `true` = نافد، `false` = متوفّر.
- يرجّع `{key, title, url, sizes}` حيث `sizes = {"S": False, "M": True, ...}`
  (القيمة = متوفّر أو لا).
- **هذي الدالة هي اللي تتغيّر لكل موقع جديد** (طريقة الكشف مختلفة لكل منصة).

#### `perform_check(token, chat_id, products, watch_sizes)` — فحص واحد
1. يقرأ كل المنتجات (`collect_product`).
2. يحمّل الحالة السابقة (`load_state`).
3. **أول تشغيل (first run):** يحفظ baseline ولا يرسل تنبيهات.
4. غير كذا: يقارن كل مقاس مراقَب — لو `now_available && !was_available` →
   يضيف تنبيه فوري ويرسله.
5. يحفظ الحالة المدمجة (`save_state`). ← **هنا تتحدّث الحالة بعد كل فحص**،
   عشان ما يتكرّر نفس التنبيه بين فحوصات نفس التشغيل.
6. **ملاحظة مهمة:** الملخص **لا يُرسل هنا** — يُرسل مرة واحدة في `main()`.

#### `build_summary(current, watch_sizes, fetch_failures, now_ksa, newly_available)`
يبني نص رسالة الملخص:
- 🕒 وقت الفحص بتوقيت السعودية (`Asia/Riyadh`).
- حالة كل منتج (✅ متوفّر / ❌ نافد) لكل مقاس مراقَب.
- 🆕 قائمة التوفّر الجديد هذا التشغيل (أو "ما فيه توفّر جديد").
- ⚠️ تنبيه لو فشلت قراءة بعض المنتجات.

#### `main()` — اللوب وإرسال الملخص
1. يقرأ المتغيّرات: `SEND_SUMMARY`, `CHECKS_PER_RUN`, `CHECK_INTERVAL_SECONDS`.
2. يحدّد `want_summary = SEND_SUMMARY=1 OR مرّت 3 ساعات` (fallback زمني).
3. ياخذ **لقطة (snapshot)** للمقاسات المتوفّرة قبل اللوب (عشان يعرف "الجديد").
4. **اللوب:** يكرّر `perform_check` عدد `CHECKS_PER_RUN` مرّة، بنوم
   `CHECK_INTERVAL_SECONDS` بينها (افتراضياً ٤ فحوصات × ١٥ دقيقة = تغطية ساعة).
5. بعد اللوب: لو `want_summary` → يبني الملخص ويرسله **مرة واحدة**، ويسجّل الوقت.

### آلية منع التكرار (dedup) — مهمة جداً
- التنبيه الفوري يعتمد على **مقارنة الحالة الحالية بالمحفوظة**.
- الحالة تُحفظ **بعد كل فحص** → لو نزل المقاس في الفحص ١، يتحدّث الحالة، فالفحص
  ٢/٣/٤ ما يشوفه "جديد" → لا تكرار.
- عبر التشغيلات: الحالة مكوميتة في المستودع، فالتشغيل الجاي يبدأ من آخر حالة.

### `state/known_stock.json` — شكل الحالة
```json
{
  "p51278165": {
    "key": "p51278165",
    "title": "تيشيرت قطني هيذر رمادي",
    "url": "https://beyondfit-sa.com/.../p51278165",
    "sizes": { "S": false, "M": false, "L": false, "XL": false, "2XL": true }
  }
}
```
> `sizes` القيمة = **متوفّر** (true) أو **نافد** (false). البوت يكوميت هذا الملف
> بعد كل تشغيل عبر خطوة "Commit and push updated state" في الـ workflow.

### `.github/workflows/monitor.yml` — كيف يترابط
- **`on.schedule`** (`11 * * * *`): فحص ساعي (fallback).
- **`on.workflow_dispatch`**: إطلاق يدوي من واجهة GitHub (مع خيار `summary`).
- **`on.repository_dispatch` (types: `summary`, `check`)**: إطلاق خارجي عبر API
  (هذا اللي يستخدمه cron-job.org).
- **بيئة التشغيل (env):**
  - `SEND_SUMMARY` = `1` لو الإطلاق `summary` أو الخيار اليدوي مفعّل.
  - `CHECKS_PER_RUN` = `1` لإطلاقات الملخص (فحص سريع ووقت دقيق)، `4` للتغطية.
  - `CHECK_INTERVAL_SECONDS` = `900` (١٥ دقيقة).
  - `PYTHONUNBUFFERED=1` لبثّ السجلّات لحظياً.
- **`timeout-minutes: 55`** — لأن تشغيل التغطية ~٤٥ دقيقة (معظمه نوم).
- **`concurrency` group** مع `cancel-in-progress: false` — يمنع تداخل تشغيلين
  (الثاني ينتظر بدل ما يشتغلون مع بعض).
- **`permissions: contents: write`** — عشان يكوميت ملف الحالة.

### تدفّق كامل (end-to-end)
```
cron-job.org (كل 3 ساعات بتوقيت دقيق)
   │  POST /dispatches {"event_type":"summary"}
   ▼
GitHub repository_dispatch  →  workflow يشتغل
   │  env: SEND_SUMMARY=1, CHECKS_PER_RUN=1
   ▼
monitor.py main()
   ├─ perform_check() ── يقرأ المنتجات ── تنبيه فوري لو فيه تحوّل ── يحفظ الحالة
   └─ build_summary() ── يرسل ملخص واحد لتيليجرام
   ▼
git commit + push  →  state/known_stock.json محدّث في المستودع
```

---

## 3) آلية الجدولة

### المشكلة: جدولة GitHub غير دقيقة
`schedule` (cron) في GitHub Actions على الخطط المجانية **متأخّرة وغير مضمونة**:
- تتأخّر عادة ١٠–٤٠ دقيقة.
- أحياناً **تُلغى تماماً** وقت الضغط العالي (شفنا فترة ١٢ ساعة بدون أي تشغيل).
- ما تقدر تعتمد عليها لتوقيت دقيق.

### الحل: مُطلِق خارجي دقيق (cron-job.org)
نخلي خدمة مجانية ([cron-job.org](https://cron-job.org)) تضرب GitHub API بتوقيت
مضبوط عبر **`repository_dispatch`**، والجدولة في GitHub تبقى **fallback** فقط.

### القيم بالضبط

**الطلب (curl):**
```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <YOUR_GITHUB_TOKEN>" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/Malkhwaiter/beyondfit-monitor/dispatches \
  -d '{"event_type":"summary"}'
```
- **النجاح = HTTP 204** (بدون محتوى).

**إعدادات cron-job.org:**

| الحقل | القيمة |
|------|--------|
| URL | `https://api.github.com/repos/Malkhwaiter/beyondfit-monitor/dispatches` |
| Method | `POST` |
| Schedule (cron) | `0 */3 * * *` (كل ٣ ساعات) |
| Timezone | `Asia/Riyadh` |
| Body | `{"event_type":"summary"}` |

**Headers:**
| Key | Value |
|-----|-------|
| `Accept` | `application/vnd.github+json` |
| `Authorization` | `Bearer <YOUR_GITHUB_TOKEN>` |
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

> `event_type` لازم يطابق واحد من `types` في الـ workflow (`summary` أو `check`).
> `summary` = فحص سريع + ملخص. `check` = فحص بدون ملخص.

---

## 4) إعادة الاستخدام — دليل خطوة بخطوة

لمراقبة **موقع أو منتج جديد** بنفس الطريقة:

### الخطوة ١: انسخ المشروع كقالب
```bash
cp -r beyondfit-monitor my-new-monitor
cd my-new-monitor
rm -rf .git state/*.json     # ابدأ بحالة نظيفة
git init
```

### الخطوة ٢: عدّل منطق الكشف في `monitor.py`
هذا الجزء **يتغيّر حسب الموقع** (شوف [القسم ٥](#5-حسب-نوع-الموقع)):
1. افتح صفحة المنتج في المتصفح → **View Source** (أو `curl <url> -o page.html`).
2. ابحث عن بيانات المقاسات/التوفّر:
   - **Salla:** عنصر `<salla-product-options>` فيه JSON بعلم `is_out`.
   - **منصة ثانية:** ابحث عن `application/ld+json`، أو `__NEXT_DATA__`، أو
     `data-*` attributes، أو API داخلي.
3. عدّل `collect_product()` و`parse_sizes()` ليطابق بنية الموقع الجديد.
4. **اختبر القراءة محلياً قبل أي شي:**
   ```bash
   python3 -c "import monitor; print(monitor.collect_product('<URL>'))"
   ```
   تأكّد إن `sizes` تطلع صح (قارنها بالمتصفح).

### الخطوة ٣: عدّل `products.json`
```json
{
  "watch_sizes": ["M"],
  "products": [
    "https://example.com/product-1",
    "https://example.com/product-2"
  ]
}
```

### الخطوة ٤: أنشئ بوت تيليجرام (لو ما عندك)
1. كلّم [@BotFather](https://t.me/BotFather) → `/newbot` → خذ **التوكن**.
2. أرسل رسالة لبوتك، ثم افتح
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → خذ `chat.id`.

### الخطوة ٥: أنشئ مستودع GitHub (public = مجاني)
- عبر الموقع: github.com/new → اسم المستودع → **Public** → Create.
- ثم محلياً:
  ```bash
  git add -A && git commit -m "initial monitor"
  git branch -M main
  git remote add origin https://github.com/<USER>/<REPO>.git
  git push -u origin main
  ```
> **ليش public؟** المستودعات العامة عندها دقائق Actions غير محدودة مجاناً.
> اللوب (٤ فحوصات/ساعة) يستهلك ~٣٢ ألف دقيقة/شهر — تتجاوز الـ ٢٠٠٠ المجانية
> للمستودعات الخاصة بكثير. الأسرار محفوظة مشفّرة فلا مشكلة أمنية.

### الخطوة ٦: اضبط GitHub Secrets
في المستودع: **Settings → Secrets and variables → Actions → New repository secret**:
- `TELEGRAM_BOT_TOKEN` = توكن البوت
- `TELEGRAM_CHAT_ID` = رقم المحادثة

وفعّل: **Settings → Actions → General → Workflow permissions → Read and write**.

> أو برمجياً (يحتاج تشفير libsodium):
> ```bash
> # احصل على public key للمستودع ثم شفّر القيمة بـ sealed box (PyNaCl)
> # شوف السكربت اللي استخدمناه سابقاً في تاريخ المشروع
> ```

### الخطوة ٧: أنشئ Fine-grained Token (أقل صلاحية)
1. الرابط: **https://github.com/settings/personal-access-tokens/new**
2. **Token name:** `<repo>-cron`
3. **Expiration:** ٩٠ يوم (أو حسب رغبتك)
4. **Resource owner:** حسابك
5. **Repository access:** **Only select repositories** → اختر مستودعك فقط
6. **Permissions → Repository permissions → Contents → Read and write**
   (Metadata: Read تنضاف تلقائياً)
7. **Generate token** → انسخ `github_pat_…`

### الخطوة ٨: اربط cron-job.org
- أنشئ Cronjob جديد بالقيم من [القسم ٣](#3-آلية-الجدولة)، مع تعديل الـ URL
  ليشير لمستودعك: `.../repos/<USER>/<REPO>/dispatches`.
- الصق التوكن في هيدر `Authorization` بعد `Bearer `.
- اضغط **Test run** → لازم يرجّع **204**.

### الخطوة ٩: تحقّق
```bash
# اختبار يدوي للملخص
curl -X POST -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <TOKEN>" \
  https://api.github.com/repos/<USER>/<REPO>/dispatches \
  -d '{"event_type":"summary"}'
# 204 + ملخص يوصل تيليجرام = تمام ✅
```

---

## 5) حسب نوع الموقع

أهم سؤال قبل أي مشروع جديد: **هل بيانات التوفّر موجودة في الـ HTML الثابت، ولا
تُحمّل بـ JavaScript بعد فتح الصفحة؟** الجواب يحدّد الطريقة كلها.

### كيف تعرف؟
```bash
curl -sL "<URL>" -o page.html
grep -i "المقاس\|size\|in_stock\|is_out\|sold" page.html
```
- لو لقيت بيانات المقاسات/التوفّر في الناتج → **HTML ثابت** (سهل).
- لو ما لقيت إلا هيكل فاضي / `<div id="root"></div>` → **JavaScript** (يحتاج متصفح).

### النوع أ: HTML ثابت / sitemap (مثل Beyondfit/Salla) ✅ المفضّل
- البيانات **مضمّنة في الـ HTML من السيرفر** (server-rendered).
- الأداة: `requests` + parsing (regex / `BeautifulSoup` / `json.loads`).
- **سريع، خفيف، يشتغل على GitHub Actions بدون متصفح.**
- أمثلة على أماكن البيانات:
  - Salla: `<salla-product-options options="...">` (JSON).
  - مواقع Next.js: `<script id="__NEXT_DATA__">`.
  - عام: `<script type="application/ld+json">` (Schema.org availability).
  - sitemap: `sitemap.xml` لاكتشاف صفحات/منتجات جديدة.

### النوع ب: JavaScript-rendered (يحتاج Playwright)
- الصفحة تجيب البيانات بـ API بعد التحميل، فالـ HTML الأولي ما فيه المقاسات.
- الأداة: **Playwright** (متصفح حقيقي headless).
- أثقل وأبطأ، وعلى GitHub Actions يحتاج تثبيت متصفح (`playwright install chromium`).
- مثال (نمط مبسّط):
  ```python
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
      b = p.chromium.launch(headless=True)
      pg = b.new_page(); pg.goto(URL, wait_until="networkidle")
      sizes = pg.evaluate("() => /* اقرأ أزرار المقاسات من DOM */")
      b.close()
  ```
- **بديل أذكى:** بدّل ما ترندر، دوّر على الـ **API الداخلي** اللي يضربه الموقع
  (Network tab في DevTools) واضربه مباشرة بـ `requests` — أسرع وأخف من Playwright.

### قاعدة القرار
> جرّب `requests` + parsing أول. لو البيانات مو في الـ HTML، دوّر على API داخلي.
> آخر حل (وأثقلها) = Playwright. **في حالتنا (Salla) النوع أ كفى وتأكّدنا منه
> بمقارنة مع متصفح حقيقي — مطابق ١٠٠٪.**

---

## 6) استكشاف الأخطاء

| المشكلة | السبب المحتمل | الحل |
|---------|---------------|------|
| **404 من `/dispatches`** | اسم المستودع/المستخدم غلط في الـ URL، أو المستودع private والتوكن ما يوصله | تأكّد من `repos/<USER>/<REPO>/dispatches` بالضبط؛ تأكّد إن التوكن له وصول للمستودع |
| **401 Bad credentials** | توكن خطأ/منتهي/فيه مسافة زائدة | جدّد التوكن؛ تأكّد إنه `Bearer <token>` بدون أقواس ولا مسافات زايدة |
| **403 Forbidden** | التوكن ما عنده صلاحية `Contents: write` | عدّل صلاحيات الـ fine-grained token → Contents: Read and write |
| **204 رجع لكن ما اشتغل workflow** | `event_type` ما يطابق `types` في الـ workflow | لازم `summary` أو `check` بالضبط (حسّاس لحالة الأحرف) |
| **الملخص ما يوصل تيليجرام** | Secrets غلط، أو البوت ما بدأت محادثة معه | تأكّد من `TELEGRAM_BOT_TOKEN`/`CHAT_ID` في Secrets؛ أرسل رسالة للبوت أول |
| **الجدولة (schedule) تتأخر/تختفي** | قيد معروف في GitHub المجاني | اعتمد على cron-job.org للتوقيت الدقيق؛ الـ schedule fallback فقط |
| **الـ workflow يُقتل بعد دقائق** | `timeout-minutes` أقل من مدة اللوب | ارفعه (٥٥ يكفي لـ ٤ فحوصات × ١٥ دقيقة) |
| **القراءة ترجّع فاضي / مقاسات غلط** | الموقع غيّر بنيته، أو البيانات JS | افحص الـ HTML من جديد؛ عدّل `parse_sizes`؛ راجع [القسم ٥](#5-حسب-نوع-الموقع) |
| **تنبيهات مكرّرة** | الحالة ما تُحفظ/تُكوميت | تأكّد من خطوة "Commit and push state" و`permissions: contents: write` |
| **push رفض (fast-forward)** | البوت كوميت حالة عن بُعد | `git pull --rebase` ثم `git push` |

**أوامر تشخيص مفيدة:**
```bash
# هل القراءة تشتغل؟
python3 -c "import monitor; print(monitor.collect_product('<URL>'))"

# آخر تشغيلات الـ workflow
curl -s -H "Authorization: Bearer <TOKEN>" \
  "https://api.github.com/repos/<USER>/<REPO>/actions/runs?per_page=5" \
  | python3 -c "import json,sys;[print(r['event'],r['status'],r['conclusion']) for r in json.load(sys.stdin)['workflow_runs']]"
```

---

## 7) نقاط الأمان

- 🔑 **استخدم Fine-grained token بأقل صلاحية:** مستودع واحد فقط + `Contents:
  write` فقط. **لا تستخدم classic token بـ scope `repo`** (يعطي صلاحية واسعة على
  كل مستودعاتك). لا يوجد صلاحية "Actions فقط" تكفي لـ `repository_dispatch` —
  المطلوب تحديداً `Contents: write`.
- 🔒 **الأسرار في GitHub Secrets، مو في الكود:** `TELEGRAM_BOT_TOKEN` و
  `TELEGRAM_CHAT_ID` تُخزّن مشفّرة في إعدادات المستودع. **حتى لو المستودع public،
  الـ Secrets تبقى سرية** ولا تظهر في السجلّات.
- 🚫 **لا تكتب أي توكن في ملفات المشروع** (ولا في `products.json` ولا أي مكان
  يتكوميت). راجع الكود قبل أي push.
- ⏰ **جدّد التوكن عند انتهائه:** الـ fine-grained token له تاريخ انتهاء. لو وقف
  cron-job.org فجأة، أول شي تأكّد إن التوكن ما انتهى → جدّده من نفس الرابط وحدّث
  قيمته في cron-job.org. **تحديث التوكن لا يحتاج تغيير أي شي في الكود.**
- 🔁 **عند تسريب توكن:** احذفه فوراً من
  [github.com/settings/tokens](https://github.com/settings/tokens) (وللبوت:
  `/revoke` في BotFather)، وأنشئ بديل. الأسرار في GitHub تبقى سليمة.
- 🌐 **خصوصية المستودع العام:** أي أحد يشوف الكود وقائمة الروابط المُراقَبة (مو
  حساسة عادة). لو فيه شي ما تبي يبين، خلّه في متغيّر/سرّ بدل ما يتكوميت.

---

> **تذكير سريع للمستقبل:** القلب اللي يتغيّر لكل موقع جديد = دالة
> `collect_product()` / `parse_sizes()`. كل شي ثاني (الحالة، التنبيه، الملخص،
> الجدولة، الأمان) قالب ثابت تعيد استخدامه كما هو.
