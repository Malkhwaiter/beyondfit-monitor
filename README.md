# beyondfit-monitor

يراقب منتجات محددة على [beyondfit-sa.com](https://beyondfit-sa.com) (متجر Salla)
ويرسل تنبيه **Telegram** أول ما يتحول مقاسك من **نافد → متوفر**. يشتغل تلقائياً
كل ساعة على GitHub Actions — بدون ما يكون جهازك شغّال.

## كيف يشتغل

1. لكل منتج في `products.json`، يجيب صفحة المنتج ويقرأ بيانات المقاسات
   المضمّنة في عنصر `<salla-product-options>` (كل مقاس له علم `is_out`).
2. يقارن توفر المقاسات المطلوبة (`watch_sizes`، الافتراضي `M`) مع آخر حالة
   محفوظة في `state/known_stock.json`.
3. لكل مقاس تحوّل من نافد إلى متوفر، يرسل رسالة Telegram.
4. يحفظ الحالة الجديدة في المستودع عشان التشغيل الجاي يعرف إيش كان متوفر.

أول تشغيل يحفظ baseline فقط ولا يرسل أي تنبيه. كذلك ما يكرّر التنبيه طول ما
المقاس باقٍ متوفر — ينبّه مرة واحدة عند كل تحوّل نافد→متوفر.

## التعديل على المنتجات والمقاسات

عدّل `products.json`:

```json
{
  "watch_sizes": ["M"],
  "products": [
    "https://beyondfit-sa.com/.../p51278165",
    "https://beyondfit-sa.com/.../p745487699"
  ]
}
```

## التشغيل محلياً

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="<bot token>"
export TELEGRAM_CHAT_ID="<chat id>"
python3 monitor.py
```

## إعداد Telegram

1. كلّم [@BotFather](https://t.me/BotFather) وأنشئ بوت جديد (`/newbot`) — يعطيك
   `TELEGRAM_BOT_TOKEN`.
2. ابدأ محادثة مع بوتك (أرسل له أي رسالة)، بعدها افتح
   `https://api.telegram.org/bot<TOKEN>/getUpdates` وخذ `chat.id` —
   هذا `TELEGRAM_CHAT_ID`.

## الأسرار (GitHub)

أضفها في **Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

وفعّل **Settings → Actions → General → Workflow permissions → Read and write
permissions** عشان الـ workflow يقدر يحفظ ملف الحالة.

## تشغيل يدوي

```bash
gh workflow run monitor.yml
gh run list --workflow=monitor.yml
```
