// GATE 4 RESEARCH BUILD — FROZEN DATA · rev G4-R1 · base 3B.1 · frozen 2026-07-16
// Customer-visible content only: no internal placeholders, no unapproved care instructions.
window.GATE4 = {
rev: "G4-R1 · base 3B.1 · frozen 1405/04/25",
proto: {
happy: [
 {label:"T1 · PRODUCT — TRUST PANEL", flow:"A", blocks:[
  {k:"appbar", t:"غذای خشک گربه", back:true},
  {k:"photo", h:120, cap:"product"},
  {k:"badges", items:[{t:"● آمادهٔ سفارش", tone:"pos"},{t:"اصالت: تأییدشده توسط تأمین‌کننده", tone:"pos"}]},
  {k:"title", t:"غذای خشک گربهٔ بالغ — سالمون ۲ کیلوگرم"},
  {k:"kv", rows:[["قیمت پلتفرم","۲٬۴۸۰٬۰۰۰ تومان"],["قیمت مرجع بازار","۳٬۹۰۰٬۰۰۰ تومان"],["صرفه‌جویی","۳۶٪ نسبت به قیمت مرجع"],["بازبینی قیمت مرجع","۱۲ تیر ۱۴۰۵"],["کشور تأمین‌کننده","آلمان — هویت تأمین‌کننده محفوظ"],["تحویل","حداکثر ۱۴ روز پس از پرداخت"],["تاریخ مصرف در تحویل","حداقل ۶ ماه — تضمینی"]]},
  {k:"btn", t:"خرید و پرداخت", kind:"primary", tap:1}]},
 {label:"ORDER PLACED", flow:"A", blocks:[
  {k:"check", t:"پرداخت انجام شد", sub:"سفارش #۱۴۰۵-۰۷۳۲ · ۱۳ تیر ۱۴۰۵"},
  {k:"kv", rows:[["مبلغ پرداخت‌شده","۲٬۴۸۰٬۰۰۰ تومان"],["سررسید تحویل","۲۷ تیر ۱۴۰۵"],["لغو رایگان","تا آغاز تأمین"]]},
  {k:"text", t:"این غذا برای کیست؟ (برنامه‌ریزی اختیاری)"},
  {k:"pills", opts:[{t:"پیشی", tap:2},{t:"فعلاً هیچ‌کدام", tap:2}]}]},
 {label:"T2 · TODAY — INCOMING", flow:"B", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"food", tone:"info", badge:"◐ در راه", t:"سالمون ۲ کیلوگرم", sub:"در حال تأمین · سررسید ۲۷ تیر", rows:[], foot:"تخمین روزهای غذا پس از تحویل و باز شدن کیسه آغاز می‌شود", cta:""},
  {k:"btn", t:"دیدن سفر سفارش", kind:"brass", tap:3},
  {k:"gstrip", t:"باغِ پیشی — زمین آماده است", sub:"", water:false},
  {k:"nav", a:0}]},
 {label:"سفر سفارش", flow:"S", blocks:[
  {k:"appbar", t:"سفر سفارش", sub:"#۱۴۰۵-۰۷۳۲"},
  {k:"badges", items:[{t:"برنامه‌ریزی‌شده برای پیشی · قابل تغییر", tone:"line"}]},
  {k:"timeline", items:[{s:"done", t:"پرداخت تأیید شد", sub:"۱۳ تیر، ۱۸:۴۲"},{s:"done", t:"تأمین آغاز شد", sub:"۱۴ تیر، ۱۰:۰۵"},{s:"now", t:"در مسیر بین‌المللی", sub:"۱۶ تیر، ۰۹:۳۰"},{s:"wait", t:"تحویل", sub:"سررسید ۲۷ تیر"}]},
  {k:"btn", t:"شبیه‌سازی: تحویل شد", kind:"primary", tap:4},
  {k:"btn", t:"بازگشت به امروز", kind:"quiet", tap:2}]},
 {label:"T3 · DELIVERED → OPENING", flow:"S", blocks:[
  {k:"check", t:"تحویل شد", sub:"به انبار خانه — نگشوده، بدون تخمین"},
  {k:"text", t:"کیسه را باز کردید؟ روزی حدوداً چقدر می‌خورد؟"},
  {k:"pills", opts:[{t:"باز شد — سهم روزانه را می‌گویم", tap:5},{t:"باز شد — نمی‌دانم", tap:8}]},
  {k:"note", t:"«نمی‌دانم» همیشه پاسخ معتبری است."},
  {k:"btn", t:"هنوز باز نشده — نگشوده بماند", kind:"quiet", tap:2}]},
 {label:"T4 · TODAY — PER-PET ESTIMATE", flow:"B", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"meter", big:"~۲۸ روز", band:"بازهٔ ۲۵ تا ۳۱ روز", conf:"اطمینان: متوسط", src:"سهم روزانه — گفتهٔ شما", cta:""},
  {k:"btn", t:"جزئیات غذاسنج", kind:"brass", tap:6},
  {k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"", water:true},
  {k:"nav", a:0}]},
 {label:"METER — ONE-TAP CORRECTION", flow:"C", blocks:[
  {k:"appbar", t:"غذاسنجِ پیشی", back:true},
  {k:"meter", big:"~۲۸ روز", band:"بازهٔ ۲۵ تا ۳۱ روز", conf:"اطمینان: متوسط", src:"باز شده — ثبت‌شده · سهم گفتهٔ شما", cta:""},
  {k:"text", t:"به‌نظرتان درست نیست؟ الان چقدر مانده؟"},
  {k:"pills", cols:2, opts:[{t:"▮▮▮▮ پر", tap:7},{t:"▮▮▮▯ بیش از نصف", tap:7},{t:"▮▮▯▯ کمتر از نصف", tap:7},{t:"▮▯▯▯ ته کیسه", tap:7}]},
  {k:"note", t:"اصلاح شما همین حالا اعمال می‌شود و نرخ مصرف برای کیسه‌های بعدی یاد گرفته می‌شود."},
  {k:"btn", t:"بازگشت", kind:"quiet", tap:5}]},
 {label:"CALM END", flow:"B", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"toast", t:"بازتنظیم شد ✓ — نرخ مصرف یاد گرفته شد"},
  {k:"meter", big:"~۱۲ روز", band:"بازهٔ ۱۱ تا ۱۴ روز — باریک‌تر", conf:"اطمینان: بالا", src:"اصلاحِ شما", cta:""},
  {k:"text", t:"امروز دیگر هیچ کاری لازم نیست.", dim:true},
  {k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"", water:true},
  {k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},
  {k:"nav", a:0}]},
 {label:"T3 · UNKNOWN — HOUSEHOLD BAND", flow:"C", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"band", label:"تخمین در سطح خانه — سهم‌ها نامشخص", right:"۱۸ تا ۴۲ روز", from:12, w:58, striped:true},
  {k:"text", t:"چون «نمی‌دانم» گفتید، عددِ به‌تفکیک پیشی نمایش داده نمی‌شود — بازه صادقانه پهن است.", dim:true},
  {k:"btn", t:"دیدن انبار خانه", kind:"brass", tap:9},
  {k:"btn", t:"سهم روزانه را می‌گویم — بازه باریک شود", kind:"quiet", tap:5},
  {k:"gstrip", t:"باغِ پیشی — زمین آماده است", sub:"", water:false},
  {k:"nav", a:0}]},
 {label:"T5 · SHARED HOUSEHOLD INVENTORY", flow:"G", blocks:[
  {k:"appbar", t:"انبار خانه"},
  {k:"kv", t:"سالمون ۲ کیلوگرم — باز", rows:[["مالکیت","خانه"],["مصرف","پیشی + رکس — مشترک"],["باز شده","امروز — ثبت‌شده"],["سهم‌ها","نامشخص — «نمی‌دانم»"]]},
  {k:"band", label:"تخمین مشترک در سطح خانه", right:"۱۸ تا ۴۲ روز", from:12, w:58, striped:true},
  {k:"note", t:"کیسه مالِ خانه است؛ خوردن مالِ حیوان‌ها. تا وقتی سهم‌ها نامشخص است، عددی به‌تفکیک هر حیوان نمایش داده نمی‌شود."},
  {k:"btn", t:"تعیین سهم‌ها", kind:"brass", tap:5},
  {k:"btn", t:"بازگشت", kind:"quiet", tap:8},
  {k:"btn", t:"شروع دوباره", kind:"text", tap:0},
  {k:"nav", a:1}]}
],
exception: [
 {label:"T6a · REORDER — OUTCOME FIRST", flow:"D", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"warn", t:"در سناریوی کندتر، غذا ممکن است پیش از رسیدن کیسهٔ جدید تمام شود", tone:"warm"},
  {k:"kv", rows:[["غذای باقی‌مانده","~۱۶ تا ۲۱ روز · تخمینی"],["تحویل این پیشنهاد","۷ تا ۱۲ روز + حاشیهٔ اطمینان"]]},
  {k:"btn", t:"دیدن گزینه‌ها", kind:"primary", tap:2},
  {k:"btn", t:"چطور محاسبه شد؟", kind:"text", tap:1},
  {k:"nav", a:0}]},
 {label:"HOW CALCULATED — ON REQUEST", flow:"D", blocks:[
  {k:"appbar", t:"چطور محاسبه شد؟", back:true},
  {k:"kv", rows:[["بدبینانه‌ترین تخمین غذا","۱۶ روز"],["دیرترین تحویل وعده‌شده","۱۲ روز"],["حاشیهٔ اطمینان","۵ روز"],["نتیجه","کمتر از صفر → پیشنهاد: همین هفته"]]},
  {k:"btn", t:"بازگشت", kind:"quiet", tap:0}]},
 {label:"OPTIONS — UNAVAILABLE", flow:"D", blocks:[
  {k:"appbar", t:"گزینه‌های سفارش", back:true},
  {k:"badges", items:[{t:"○ سالمون ۲ کیلوگرم — موقتاً ناموجود", tone:"mute"}]},
  {k:"text", t:"در حال حاضر تأمین‌کنندهٔ تأییدشده‌ای در دسترس نیست. به‌محض فراهم شدن خبر می‌دهیم.", dim:true},
  {k:"btn", t:"به من خبر بده", kind:"primary", tap:3},
  {k:"kv", t:"جایگزین: بوقلمون ۲ کیلوگرم", rows:[["قیمت","۲٬۲۹۰٬۰۰۰ تومان"],["تحویل","۵ تا ۹ روز · دلیل پیشنهاد: سریع‌تر"]]},
  {k:"btn", t:"جای دیگری خریدم", kind:"quiet", tap:4}]},
 {label:"NOTIFY CONFIRMED — NO ORDER", flow:"B", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"toast", t:"ثبت شد ✓ — فقط یک اعلان؛ هیچ سفارشی ثبت نشد"},
  {k:"meter", big:"~۱۸ روز", band:"بازهٔ ۱۶ تا ۲۱ روز", conf:"اطمینان: متوسط", src:"سالمون ۲ کیلو", cta:""},
  {k:"text", t:"به‌محض موجود شدن، همین‌جا خبر می‌دهیم.", dim:true},
  {k:"gstrip", t:"باغِ پیشی — آرام", sub:"", water:true},
  {k:"btn", t:"جای دیگری خریدم", kind:"quiet", tap:4},
  {k:"btn", t:"سناریوی بعدی: سفارشِ در راه (T6b)", kind:"text", tap:5},
  {k:"nav", a:0}]},
 {label:"BOUGHT ELSEWHERE — FIRST-CLASS", flow:"D", blocks:[
  {k:"check", t:"خریدید؟ خوب است", sub:"مهم این است که غذای پیشی به ته نمی‌رسد"},
  {k:"btn", t:"افزودن به انبار خانه", kind:"primary", tap:7},
  {k:"note", t:"غذاسنج با همان کیسه ادامه می‌دهد — فرقی نمی‌کند از کجا خریده‌اید."}]},
 {label:"T6b · EXISTING ORDER — IN TRANSIT", flow:"S", blocks:[
  {k:"appbar", t:"سفر سفارش", sub:"#۱۴۰۵-۰۷۳۲"},
  {k:"kv", rows:[["وضعیت","◐ در مسیر بین‌المللی"],["سررسید تحویل","۲۷ تیر ۱۴۰۵"]]},
  {k:"timeline", items:[{s:"done", t:"پرداخت تأیید شد", sub:"۱۳ تیر، ۱۸:۴۲"},{s:"done", t:"تأمین آغاز شد", sub:"۱۴ تیر، ۱۰:۰۵"},{s:"now", t:"در مسیر بین‌المللی", sub:"۱۶ تیر، ۰۹:۳۰"},{s:"wait", t:"گمرک، بازرسی و تحویل", sub:"در انتظار"}]},
  {k:"btn", t:"به‌روزرسانی وضعیت (شبیه‌سازی)", kind:"primary", tap:6},
  {k:"btn", t:"شروع دوباره", kind:"text", tap:0}]},
 {label:"DELAYED — FACTS WITH DATES", flow:"S", sheet:true, blocks:[
  {k:"warn", t:"سفارش شما دیرتر می‌رسد", sub:"حمل بین‌المللی بیش از برآورد طول کشیده؛ تأمین ادامه دارد و سفارش لغو نشده است", tone:"warm"},
  {k:"kv", rows:[["سررسید اولیه","۲۷ تیر — گذشته"],["برآورد جدید","۳ مرداد ۱۴۰۵"]]},
  {k:"note", t:"اگر غذای فعلی زودتر تمام شود، غذاسنج همان موقع خبر می‌دهد و گزینه‌های سریع‌تر را نشان می‌دهیم."},
  {k:"btn", t:"متوجه شدم", kind:"primary", tap:7},
  {k:"btn", t:"گفت‌وگو با پشتیبانی", kind:"quiet", tap:7}]},
 {label:"TODAY — SETTLED", flow:"B", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"food", tone:"info", badge:"◐ در راه", t:"سالمون ۲ کیلوگرم", sub:"برآورد جدید: ۳ مرداد ۱۴۰۵", rows:[], foot:"", cta:""},
  {k:"meter", big:"~۱۸ روز", band:"بازهٔ ۱۶ تا ۲۱ روز", conf:"اطمینان: متوسط", src:"سالمون ۲ کیلو", cta:""},
  {k:"text", t:"وضعیت روشن ماند و تصمیم با شما بود.", dim:true},
  {k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},
  {k:"nav", a:0}]}
],
garden: [
 {label:"T7 · CHECK-IN — FINAL NIGHT", flow:"E", blocks:[
  {k:"appbar", t:"چک‌این شب پایانی", back:true},
  {k:"title", t:"امشب چطور بود؟"},
  {k:"pills", opts:[{t:"خوب بود", tap:1},{t:"مثل همیشه", tap:1}]},
  {k:"text", t:"شبِ آخرِ مسیر مراقبتیِ پیشی", dim:true},
  {k:"note", t:"فقط در طول مسیر می‌پرسیم — نه همیشه."}]},
 {label:"COMPLETION → MEMORY → REVEAL", flow:"E", blocks:[
  {k:"appbar", t:"مسیر مراقبتیِ پیشی", badge:{t:"✓ کامل شد", tone:"pos"}},
  {k:"kv", rows:[["مسیر ۱۴شبه","در عمل ۱۶ شب — با یک مکثِ شما"],["چک‌این‌ها","۱۲ از ۱۴ شب"],["خاطره","در دفترچهٔ پیشی ثبت شد"]]},
  {k:"deep", t:"سروِ باغ آمادهٔ کاشت است", sub:"برای همیشه به همین خاطره پیوند دارد — کجا بنشیند؟", pills:[{t:"قطعهٔ شمالی", tap:2},{t:"کنار حوض", on:true, tap:2},{t:"گوشهٔ نهال‌ها", tap:2}]}]},
 {label:"GARDEN — PLANTED", flow:"F", dark:true, blocks:[
  {k:"gappbar", t:"باغِ پیشی", right:"۴ از ۷ جای‌گاه"},
  {k:"garden", v:"est"},
  {k:"gobj", t:"سرو نشست — کنار حوض", sub:"پیوند به خاطرهٔ مسیر مراقبتی", cta:""},
  {k:"btn", t:"دیدن خاطره", kind:"gold", tap:3},
  {k:"btn", t:"بازگشت به امروز", kind:"gquiet", tap:4}]},
 {label:"MEMORY DETAIL", flow:"F", dark:true, blocks:[
  {k:"gappbar", t:"خاطرهٔ سرو", right:""},
  {k:"gobj", t:"پایان مسیر مراقبتیِ پاییز", sub:"آبان ۱۴۰۵ · ۱۶ شب، با یک مکث", cta:""},
  {k:"gtext", t:"یادداشت شما: «شب ششم آرام‌تر رفتیم و رسیدیم.»"},
  {k:"btn", t:"بازگشت به باغ", kind:"gquiet", tap:2}]},
 {label:"TODAY — CALM RETURN", flow:"B", blocks:[
  {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
  {k:"meter", big:"~۲۴ روز", band:"بازهٔ ۲۰ تا ۲۸ روز", conf:"اطمینان: بالا", src:"سالمون ۲ کیلو", cta:""},
  {k:"text", t:"امروز هیچ کاری لازم نیست.", dim:true},
  {k:"gstrip", t:"سرو کنار حوض نشست", sub:"۴ از ۷ جای‌گاه", water:true},
  {k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},
  {k:"nav", a:0}]}
]
}
};
