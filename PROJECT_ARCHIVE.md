# 🗄️ PROJECT_ARCHIVE — beyondfit-monitor

> **مرجع تقني مستقل وقابل للنقل لأي مهمة مراقبة جديدة.**
> هذا الملف مكتوب بحيث ترفعه لوحده مستقبلاً وتقول «أبي أراقب X بنفس الطريقة» —
> فيه كل اللي يلزم لإحياء النمط من الصفر لأي هدف، مو بس توثيق لهذا المشروع.

**الحالة:** ✅ المهمة خلصت — جاء مقاس M واشتُريت التيشيرتات → **تقاعد البوت** (retired).
**المستودع:** `Malkhwaiter/beyondfit-monitor` (public) · آخر تحديث: 2026-06-04

---

## فهرس
1. [نظرة عامة](#1-نظرة-عامة)
2. [المعمارية القابلة لإعادة الاستخدام](#2-المعمارية)
3. [كل ملف ووش يسوي (مع الكود)](#3-الملفات)
4. [⭐ المتغيّرات اللي تعدّلها لأي هدف جديد](#4-المتغيرات)
5. [الأسرار والتوكنات (أسماء فقط)](#5-الأسرار)
6. [إعداد cron-job.org بالضبط](#6-cron-joborg)
7. [المشاكل وحلولها](#7-المشاكل)
8. [🔄 كيف أحيي هذا لهدف جديد — خطوة بخطوة](#8-الإحياء)
9. [العلاقة بـ PLAYBOOK.md](#9-playbook)

---

## 1) نظرة عامة

بوت يراقب **توفّر مقاس M** لأربعة تيشيرتات قطنية على
[beyondfit-sa.com](https://beyondfit-sa.com) (متجر **Salla**)، ويرسل تنبيه
**تيليجرام** أول ما يتحوّل المقاس من نافد → متوفّر، مع ملخص دوري للاطمئنان.
يشتغل على **GitHub Actions مجاناً** (بدون جهاز شغّال).

**النتيجة:** نجح — وصل المقاس، تم الشراء، والبوت متقاعد. هذا الأرشيف يحفظ النمط.

---

## 2) المعمارية

النمط = **٤ قطع**، كل وحدة تحل مشكلة معيّنة:

```
cron-job.org (توقيت دقيق كل 3 ساعات)
   │ POST repository_dispatch {"event_type":"summary"}
   ▼
GitHub Actions workflow ── يشغّل monitor.py
   │   • schedule ساعي (fallback لو cron-job.org وقف)
   │   • repository_dispatch (الإطلاق الخارجي الدقيق)
   ▼
monitor.py
   ├─ حلقة polling داخلية: 4 فحوصات × كل 15 دقيقة = تغطية الساعة كاملة
   ├─ لكل فحص: يقرأ التوفّر → يقارن بالحالة المحفوظة → ينبّه عند التحوّل → يحفظ
   └─ ملخص تيليجرام دوري (مرة/تشغيل عند SEND_SUMMARY أو كل 3 ساعات fallback)
   ▼
state/*.json يتكوميت للمستودع (الذاكرة بين التشغيلات)
```

**ليش كل قطعة موجودة (مهم لتعرف وش تعدّل):**

| القطعة | ليش موجودة |
|--------|-----------|
| **GitHub Actions** | تشغيل مجاني في السحابة بدون سيرفر/جهاز. (Public repo = دقائق غير محدودة مجاناً) |
| **حلقة polling داخلية** (4 فحوصات/تشغيل) | جدولة GitHub المجانية **متأخرة وغير دقيقة** — بدل ما نعتمد على 4 تشغيلات منفصلة (يتخطّى بعضها)، تشغيل واحد يغطّي الساعة بـ 4 فحوصات داخلية |
| **ملخص تيليجرام دوري** | رسالة اطمئنان تثبت إن البوت حيّ حتى لو ما تغيّر شي |
| **cron-job.org (جدولة خارجية)** | توقيت **دقيق** للملخص (GitHub cron غير مضمون). يضرب `repository_dispatch` بتوقيت مضبوط |
| **state/*.json مكوميت** | ذاكرة دائمة: يعرف وش «جديد» ويمنع تكرار التنبيه |

---

## 3) الملفات

```
beyondfit-monitor/
├── monitor.py              # كل المنطق (~442 سطر)
├── products.json           # ⭐ الإعدادات: الروابط + المقاسات المراقَبة
├── requirements.txt        # requests
├── state/
│   ├── known_stock.json    # الحالة: توفّر كل مقاس لكل منتج (يكوميته البوت)
│   └── summary_state.json  # آخر وقت أُرسل فيه ملخص (UTC) — لبوابة الـ3 ساعات
├── .github/workflows/
│   └── monitor.yml         # الجدولة + بيئة التشغيل + كوميت الحالة
├── README.md               # تشغيل + إعداد
├── PLAYBOOK.md             # مرجع معماري موسّع
└── PROJECT_ARCHIVE.md      # هذا الملف
```

### `monitor.py` — الدوال الرئيسية
- **`http_get(url)`** — يجيب الصفحة بـ `requests` (HTML ثابت، بدون JavaScript) مع إعادة محاولة.
- **`parse_sizes(doc)`** ⭐ **قلب الكشف** — يستخرج المقاسات من عنصر
  `<salla-product-options options="...">` (JSON مُرمّز داخل الـ HTML). كل مقاس
  له علم `is_out` (`true`=نافد). **هذا اللي يتغيّر لكل موقع جديد.**
- **`collect_product(url)`** — يجمع `{key,title,url,sizes}` لمنتج.
- **`perform_check(...)`** — فحص واحد: يقرأ كل المنتجات، يقارن بالحالة السابقة،
  يرسل تنبيه فوري عند تحوّل نافد→متوفّر، يحفظ الحالة (هنا منع التكرار).
- **`build_summary(...)`** — نص الملخص الدوري.
- **`main()`** — يكرّر `perform_check` بعدد `CHECKS_PER_RUN` بنوم
  `CHECK_INTERVAL_SECONDS` بينها، ثم يرسل ملخص واحد لو مطلوب.

**مقتطف الكشف الفعلي (Salla):**
```python
OPTIONS_RE = re.compile(r'<salla-product-options\s+options="(.*?)"', re.S)
SIZE_GROUP_NAMES = {"القياس", "المقاس", "مقاس", "size", "Size", "الحجم"}

def parse_sizes(doc):
    m = OPTIONS_RE.search(doc)
    if not m: return None
    groups = json.loads(html.unescape(m.group(1)))     # JSON مُرمّز داخل الـHTML
    # اختر مجموعة المقاس بالاسم، أو أول مجموعة قيمها تشبه مقاسات
    size_group = next((g for g in groups
                       if (g.get("name") or "").strip() in SIZE_GROUP_NAMES), None)
    ...
    return {v["name"].strip(): not bool(v.get("is_out", True))   # is_out=true => نافد
            for v in size_group["details"] if v.get("name")}
```

**نص التنبيه الفوري + الملخص (في `perform_check` / `build_summary`):**
```python
"🎉 <b>رجع متوفر!</b>\n\n<b>{title}</b>\nالمقاس <b>{size}</b> صار متوفر الحين.\n{url}"
"📋 <b>ملخص — beyondfit-monitor</b> ..."
```

### `products.json` ⭐
```json
{
  "watch_sizes": ["M"],
  "products": [
    "https://beyondfit-sa.com/تيشيرت-قطني-هيذر-رمادي/p51278165",
    "https://beyondfit-sa.com/تيشيرت-قطني-أبيض/p745487699",
    "https://beyondfit-sa.com/تيشيرت-قطني-أسود/p539475871",
    "https://beyondfit-sa.com/تيشيرت-قطني-حديدي/p469392708"
  ]
}
```

### `.github/workflows/monitor.yml` — النقاط المهمة
- **`on.schedule`**: `"11 * * * *"` (ساعي، fallback — مزاح عن الدقيقة :00).
- **`on.workflow_dispatch`**: إطلاق يدوي + خيار `summary`.
- **`on.repository_dispatch` types: `[summary, check]`**: الإطلاق الخارجي (cron-job.org).
- **بيئة التشغيل:**
  - `SEND_SUMMARY = 1` عند action=`summary` أو الخيار اليدوي.
  - `CHECKS_PER_RUN = 1` لإطلاقات الملخص (سريع/وقت دقيق)، `4` للتغطية.
  - `CHECK_INTERVAL_SECONDS = 900` (15 دقيقة).
- **`timeout-minutes: 55`** — لأن تشغيل التغطية ~45 دقيقة (معظمه نوم). **مهم.**
- **`concurrency` group + `cancel-in-progress: false`** — يمنع تداخل تشغيلين.
- **`permissions: contents: write`** — عشان يكوميت الحالة.
- خطوة **Commit state** تعمل `git add state`، commit، ثم push مع
  `pull --rebase` عند الفشل (تتعامل مع كوميتات البوت المتزامنة).

---

## 4) المتغيّرات

**عشان توجّه هذا النمط لأي هدف جديد، عدّل هذي فقط:**

| المتغيّر | الملف | وش تحط |
|----------|-------|--------|
| **الروابط** | `products.json` → `products` | روابط منتجات الهدف الجديد |
| **القيمة المراقَبة** | `products.json` → `watch_sizes` | مقاس/لون/أي متغيّر (`["M"]`، إلخ) |
| ⭐ **منطق الكشف** | `monitor.py` → `parse_sizes()` | **الأهم** — كيف تقرأ التوفّر من بنية الموقع الجديد (شوف القسم 8) |
| اسم مجموعة المقاس | `monitor.py` → `SIZE_GROUP_NAMES` | اسم المجموعة بلغة الموقع |
| لاحقة العنوان | `monitor.py` → `parse_title()` | لإزالة « - اسم المتجر» |
| مفتاح المنتج | `monitor.py` → `PRODUCT_ID_RE` | نمط معرّف المنتج في الرابط |
| **نص الرسائل** | `monitor.py` → `perform_check` / `build_summary` | نص التنبيه والملخص |
| التوقيت/المنطقة | `monitor.py` → `KSA_OFFSET_HOURS`, `SUMMARY_EVERY_HOURS` | فرق التوقيت وكل كم ساعة ملخص |
| الجدولة + عدد الفحوصات | `monitor.yml` → `cron`, `CHECKS_PER_RUN`, `CHECK_INTERVAL_SECONDS` | إيقاع الفحص |
| جدولة cron-job.org | (القسم 6) | كل كم يطلق الملخص |

---

## 5) الأسرار

> القيم لا تُكتب هنا أبداً — الأسماء فقط.

| السر/التوكن | وين مُعدّ | كيف تنشئه من جديد | ملاحظة |
|-------------|----------|-------------------|--------|
| `TELEGRAM_BOT_TOKEN` | GitHub repo → Settings → Secrets → Actions | [@BotFather](https://t.me/BotFather) → `/newbot` (أو `/mybots` → API Token) | ⚠️ **مشترك** مع تطبيق tracker-app — لا تلغيه لو التطبيق شغّال |
| `TELEGRAM_CHAT_ID` | نفس المكان (GitHub Secrets) | `https://api.telegram.org/bot<TOKEN>/getUpdates` → `chat.id` | نفس الشات المشترك |
| **GitHub PAT (classic)** | محلياً (git push) + إعدادات tracker-app | github.com/settings/tokens → scopes: `repo`, `workflow` | ⚠️ **مشترك** مع tracker-app — لا تلغيه لو التطبيق شغّال |
| **GitHub fine-grained token** | داخل هيدر مهمة cron-job.org | github.com/settings/personal-access-tokens/new → repo واحد + **Contents: Read/Write** | خاص بـ cron-job.org لهذا المشروع — **آمن تلغيه بعد حذف مهمة cron** |

---

## 6) cron-job.org

مهمة تضرب GitHub `repository_dispatch` بتوقيت دقيق:

| الحقل | القيمة |
|------|--------|
| **URL** | `https://api.github.com/repos/Malkhwaiter/beyondfit-monitor/dispatches` |
| **Method** | `POST` |
| **Schedule** | كل 3 ساعات — `0 */3 * * *` |
| **Timezone** | `Asia/Riyadh` |
| **Body** | `{"event_type":"summary"}` |

**Headers:**
| Key | Value |
|-----|-------|
| `Accept` | `application/vnd.github+json` |
| `Authorization` | `Bearer <GITHUB_FINE_GRAINED_TOKEN>` |
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

النجاح = **HTTP 204**. `event_type` لازم يطابق `types` في الـ workflow.

---

## 7) المشاكل وحلولها

| المشكلة | الحل |
|---------|------|
| **جدولة GitHub المجانية متأخرة/تُلغى** (فترات بدون أي تشغيل) | حلقة polling داخلية (4 فحوصات/تشغيل) + cron-job.org للتوقيت الدقيق + بوابة ملخص كل 3 ساعات fallback |
| **التكلفة**: الحلقة ~45 دقيقة/تشغيل × ساعي = آلاف الدقائق/شهر (يتجاوز 2000 المجانية للـprivate) | **خلّي المستودع public** → دقائق Actions غير محدودة مجاناً |
| **`timeout-minutes: 5` يقتل تشغيل الـ45 دقيقة** | رفعه إلى **55** |
| **push مرفوض (fast-forward)** لأن البوت يكوميت الحالة | `git pull --rebase` ثم push (الـ workflow يعيد المحاولة تلقائياً) |
| **rebase يحتاج هوية git** | `git config user.name/email` |
| **Salla يخفي المقاسات النافدة** في القائمة المرئية | الـ HTML الثابت فيه **كل** المقاسات مع `is_out` — تأكدنا بمقارنة مع متصفح حقيقي (مطابق 100%) |
| ⚠️ **أعطال runner مؤقتة من GitHub** — رسائل مثل `"The job was not acquired by Runner"` أو `Internal server error` | **مو مشكلة كود.** يطلع فشل أحمر بعد ~15 دقيقة بسبب بنية GitHub التحتية. تجاهله أو أعد التشغيل (Re-run) — التشغيل المجدول التالي يتعافى لوحده. **لا تعدّل الكود بسببه.** |

---

## 8) الإحياء

**لإحياء النمط لهدف مراقبة جديد، من الصفر:**

1. **انسخ القالب**
   ```bash
   cp -r beyondfit-monitor my-new-monitor && cd my-new-monitor
   rm -rf .git state/*.json && git init
   ```
2. **عدّل `products.json`** — روابط الهدف الجديد + `watch_sizes`.
3. ⭐ **أعد كتابة الكشف في `parse_sizes()`** حسب نوع الموقع:
   - افتح صفحة المنتج → **View Source** (أو `curl <url> -o page.html`).
   - دوّر على بيانات التوفّر:
     - **Salla**: `<salla-product-options>` فيه `is_out` (زي هذا المشروع).
     - **Next.js**: `<script id="__NEXT_DATA__">`.
     - **عام**: `<script type="application/ld+json">` (schema.org availability).
   - عدّل `parse_sizes` ليطابق البنية الجديدة.
   - **اختبر القراءة محلياً قبل أي شي:**
     ```bash
     python3 -c "import monitor; print(monitor.collect_product('<URL>'))"
     ```
   - ⚠️ لو الموقع يحمّل البيانات بـ JavaScript أو محمي ضد البوتات (Amazon/ASOS/
     علامات كبيرة) → **ما يشتغل** بهذا النمط (يحتاج متصفح/خدمة كشط مدفوعة).
     النمط مناسب لمتاجر Salla والمواقع المفتوحة المتوسطة.
4. **عدّل نص الرسائل** في `perform_check` و `build_summary`.
5. **أنشئ بوت تيليجرام** (BotFather) وخذ التوكن + chat id.
6. **أنشئ مستودع GitHub (public)** وارفع، وحط `TELEGRAM_BOT_TOKEN` +
   `TELEGRAM_CHAT_ID` في Secrets، وفعّل Workflow read/write permissions.
7. **(اختياري) cron-job.org** — مهمة بقيم القسم 6 (بدّل اسم المستودع)، مع
   fine-grained token (Contents: write) في هيدر Authorization.
8. **اختبر**: `gh workflow run monitor.yml` أو أطلق repository_dispatch، وتأكد
   إن الملخص يوصل تيليجرام.

> القلب اللي يتغيّر = **`parse_sizes()` + `products.json` + نص الرسائل**. كل شي
> ثاني (الحلقة، الحالة، التنبيه، الجدولة) قالب ثابت تعيد استخدامه كما هو.

---

## 9) PLAYBOOK

- **`PLAYBOOK.md`** = المرجع المعماري الموسّع (شرح أعمق للنمط، أنواع المواقع،
  استكشاف الأخطاء، الأمان) — كُتب وقت ما كان المشروع نشطاً.
- **`PROJECT_ARCHIVE.md`** (هذا) = سجل المشروع المتقاعد + دليل إحياء مركّز +
  التفاصيل التشغيلية (الأسرار، cron-job.org بالضبط، أعطال runner).

**وش تغيّر من وقت ما كُتب PLAYBOOK:**
- المشروع **تقاعد** (المهمة خلصت).
- نشأ تطبيق منفصل **tracker-app** (واجهة + مستودع `product-tracker` السحابي)
  يعمّم نفس النمط لأي منتج بضغطة — **يشارك نفس بوت تيليجرام ونفس GitHub PAT**.
  لذلك انتبه: إلغاء التوكنات المشتركة يكسر التطبيق إن كان شغّالاً.

---

> **للمستقبل:** ارفع هذا الملف + قُل هدفك الجديد، وأكمل من القسم 8 مباشرة.
