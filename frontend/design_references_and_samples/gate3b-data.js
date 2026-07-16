window.GATE3B = {
flows: [

{id:"A", title:"Commerce → activation", intent:"Buying never requires a pet; a paid order is «در راه» — planned assignment only, no estimate until confirmed opening.", screens:[
{id:"A1", label:"PRODUCT — READY TO ORDER", note:"Trust panel: authenticity is supplier-verified; supplier identity stays private, country shown. Saving is vs the dated reference price — evidence auditable internally. Prices/dates ● operational.", blocks:[
 {k:"appbar", t:"غذای خشک گربه", back:true},
 {k:"photo", h:150, cap:"product photo — label sharp"},
 {k:"badges", items:[{t:"● آمادهٔ سفارش", tone:"pos"},{t:"اصالت: تأییدشده توسط تأمین‌کننده", tone:"pos"}]},
 {k:"title", t:"غذای خشک گربهٔ بالغ — سالمون ۲ کیلوگرم"},
 {k:"kv", rows:[["قیمت پلتفرم","۲٬۴۸۰٬۰۰۰ تومان"],["قیمت مرجع بازار","۳٬۹۰۰٬۰۰۰ تومان"],["صرفه‌جویی","۳۶٪ نسبت به قیمت مرجع"],["بازبینی قیمت مرجع","۱۲ تیر ۱۴۰۵ ●"],["کشور تأمین‌کننده","آلمان — هویت تأمین‌کننده محفوظ"],["تحویل","حداکثر ۱۴ روز پس از پرداخت"],["تاریخ مصرف در تحویل","حداقل ۶ ماه — تضمینی"]]},
 {k:"btn", t:"افزودن به سبد و پرداخت", kind:"primary"},
 {k:"nav", a:3}]},
{id:"A2", label:"ORDER PLACED — PLANNED ASSIGNMENT", note:"Assignment before delivery is a plan, not consumption (Gate 2.1 §2).", blocks:[
 {k:"check", t:"پرداخت انجام شد", sub:"سفارش #۱۴۰۵-۰۷۳۲ · ۱۳ تیر ۱۴۰۵"},
 {k:"kv", rows:[["مبلغ پرداخت‌شده","۲٬۴۸۰٬۰۰۰ تومان"],["سررسید تحویل","۲۷ تیر ۱۴۰۵"],["لغو رایگان","تا آغاز تأمین"]]},
 {k:"text", t:"این غذا برای کیست؟ (برنامه‌ریزی اختیاری — بعداً هم می‌شود)"},
 {k:"pills", opts:[{t:"پیشی"},{t:"رکس"},{t:"فعلاً هیچ‌کدام"}]},
 {k:"note", t:"انتساب فقط برنامه‌ریزی است؛ تا تحویل و باز شدن کیسه، هیچ تخمین مصرفی شروع نمی‌شود."},
 {k:"btn", t:"دیدن سفر سفارش", kind:"brass"}]},
{id:"A3", label:"MINIMAL PROFILE — SHEET", note:"Two fields, mid-flow, skippable; everything else deferred to value moments.", sheet:true, blocks:[
 {k:"title", t:"این خرید برای کیست؟", sub:"فقط دو مورد — بقیه را هر وقت خواستید"},
 {k:"input", label:"نام", val:"پیشی"},
 {k:"pills", opts:[{t:"گربه", on:true},{t:"سگ"},{t:"دیگر"}]},
 {k:"btn", t:"ثبت و ادامه", kind:"primary"},
 {k:"btn", t:"فعلاً برای خانه — بدون ثبت حیوان", kind:"text"}]},
{id:"A4", label:"ACTIVATED — TODAY, INCOMING STATE", note:"Activation may precede delivery: the food module is an incoming status, never an estimate (= 3A-1).", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"افزودن", sp:"add"}]},
 {k:"food", tone:"info", badge:"◐ در راه", t:"سالمون ۲ کیلوگرم", sub:"سفر سفارش: در حال تأمین · مرحلهٔ ۱ از ۴", rows:[["سررسید تحویل","۲۷ تیر ۱۴۰۵"]], foot:"تخمین روزها پس از تحویل و باز شدن کیسه آغاز می‌شود", cta:"دیدن سفر سفارش"},
 {k:"event", g:"pen", t:"شنبه — نوبت واکسن سالانهٔ پیشی", sub:"ثبت‌شدهٔ شما در دفترچه"},
 {k:"gstrip", t:"باغِ پیشی — زمین آماده است", sub:"جای بعدی: سنگفرش · با تکمیل پروفایل", water:false},
 {k:"nav", a:0}]}
]},

{id:"B", title:"Today — everyday & edge states", intent:"Fixed hierarchy: identity → food status → next event → compact Garden preview. No default feeding log; an empty day is read-only.", screens:[
{id:"B1", label:"ACTIVE — 20-SECOND VISIT", note:"= 3A-2. Check-in exists only because a journey is active.", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"meter", big:"~۱۱ روز", band:"بازهٔ ۹ تا ۱۳ روز", conf:"اطمینان: متوسط", src:"سالمون ۲ کیلو · باز شده ۳ تیر", cta:"جزئیات و اصلاح"},
 {k:"event", g:"num", t:"امشب: چک‌این مسیر تغییر غذا", sub:"روز ۶ از ۱۴ · تنها درخواست امروز"},
 {k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"جای بعدی: سرو · با پایان مسیر", water:true},
 {k:"nav", a:0}]},
{id:"B2", label:"EMPTY DAY — READ-ONLY", note:"Calm by design: nothing to log, nothing to tap (Gate 2.1 §1).", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"meter", big:"~۲۴ روز", band:"بازهٔ ۲۰ تا ۲۸ روز", conf:"اطمینان: بالا", src:"همه‌چیز روبه‌راه است", cta:""},
 {k:"text", t:"امروز هیچ کاری لازم نیست.", dim:true},
 {k:"gstrip", t:"پیشی کنار حوض خوابیده", sub:"باغ آرام است", water:true},
 {k:"nav", a:0}]},
{id:"B3", label:"LOADING — SKELETON", note:"Identity paints first (cached); modules skeleton at final geometry — no spinners, no layout shift.", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"skel", h:110},
 {k:"skel", h:64},
 {k:"skel", h:76},
 {k:"nav", a:0}]},
{id:"B4", label:"MODULE ERROR — GRACEFUL", note:"One failing module never blanks Today; muted ink, not alarm red.", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"warn", t:"غذاسنج فعلاً در دسترس نیست", sub:"دوباره تلاش می‌کنیم — بقیهٔ خانه کار می‌کند", tone:"mute"},
 {k:"btn", t:"تلاش دوباره", kind:"quiet"},
 {k:"event", g:"pen", t:"شنبه — نوبت واکسن سالانهٔ پیشی", sub:"ثبت‌شدهٔ شما"},
 {k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"در دسترس", water:true},
 {k:"nav", a:0}]},
{id:"B5", label:"RETURN AFTER 3 WEEKS", note:"Warm greeting only — no guilt. Absence honestly widens the band; one small confirm narrows it.", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"text", t:"خوش برگشتید — همه‌چیز سرِ جای خودش است."},
 {k:"meter", big:"~۸ روز", band:"بازهٔ ۴ تا ۱۲ روز — پهن‌تر شده", conf:"اطمینان: پایین", src:"آخرین تأیید: ۲۳ روز پیش", cta:""},
 {k:"pills", opts:[{t:"▮▮▮▯ بیش از نصف"},{t:"▮▮▯▯ کمتر از نصف"},{t:"نمی‌دانم"}]},
 {k:"gstrip", t:"باغ منتظرتان بود — هیچ چیزی کم نشده", sub:"آب همچنان روان", water:true},
 {k:"nav", a:0}]}
]},

{id:"C", title:"Food meter — setup, shares, correction", intent:"Estimates start only at confirmed opening; shares are owner-stated or honestly unknown; heuristics never look precise.", screens:[
{id:"C1", label:"CONFIRM OPENING — SHEET", note:"The single gate that starts any estimate (Gate 2.1 §2).", sheet:true, blocks:[
 {k:"title", t:"کیسهٔ سالمون رسید — باز شد؟", sub:"تا باز نشده، فقط «نگشوده» در انبار می‌ماند"},
 {k:"pills", opts:[{t:"امروز باز شد"},{t:"چند روز پیش"},{t:"هنوز نه"}]},
 {k:"note", t:"با «هنوز نه»، هیچ تخمینی شروع نمی‌شود و بعداً از همین‌جا ادامه می‌دهید."}]},
{id:"C2", label:"REMAINING + PORTION — SHEET", note:"Quarter scale doubles as the future correction UI; «نمی‌دانم» is first-class.", sheet:true, blocks:[
 {k:"title", t:"حدوداً چقدر مانده و روزی چقدر می‌خورد؟"},
 {k:"pills", cols:2, opts:[{t:"▮▮▮▮ پر"},{t:"▮▮▮▯ بیش از نصف"},{t:"▮▮▯▯ کمتر از نصف"},{t:"▮▯▯▯ ته کیسه"}]},
 {k:"pills", opts:[{t:"سهم روزانه را می‌گویم"},{t:"نمی‌دانم"}]},
 {k:"note", t:"«نمی‌دانم» = شروع با بازهٔ پهن‌تر — بعداً با یک اصلاح باریک می‌شود."}]},
{id:"C3", label:"SHARED BAG — OWNER SHARES", note:"No automatic weight split (Gate 2.1 §4); unknown → striped household band.", blocks:[
 {k:"appbar", t:"سهم‌های کیسهٔ مشترک", back:true},
 {k:"text", t:"پیشی و رکس از یک کیسه می‌خورند. سهم‌ها را چطور ثبت کنیم؟"},
 {k:"pills", opts:[{t:"سهم هر کدام را می‌گویم"},{t:"حدودی: پیشی کمتر، رکس بیشتر"},{t:"نمی‌دانم"}]},
 {k:"band", label:"نمی‌دانم → تخمین در سطح خانه", right:"۶ تا ۱۶ روز", from:20, w:46, striped:true},
 {k:"note", t:"بازهٔ پهن و بافتِ راه‌راه یعنی: تخمین مشترک خانه، نه عدد دقیق."}]},
{id:"C4", label:"MIXED FEEDING — OWNER RATIO", note:"No fixed two-thirds assumption; the dry share comes from the owner or stays unknown.", blocks:[
 {k:"appbar", t:"ترکیب غذای پیشی", back:true},
 {k:"pills", opts:[{t:"فقط خشک"},{t:"بیشتر خشک", on:true},{t:"نصف‌نصف"},{t:"بیشتر تر"},{t:"نمی‌دانم"}]},
 {k:"text", t:"سهم خشک را خودتان مشخص می‌کنید — پیش‌فرضی در کار نیست.", dim:true},
 {k:"band", label:"بیشتر خشک — گفتهٔ شما", right:"۹ تا ۱۳ روز", from:30, w:24, striped:false}]},
{id:"C5", label:"DETAIL + ONE-TAP CORRECTION", note:"= 3A-3: band, confidence in words, provenance per input, 44px correction.", blocks:[
 {k:"appbar", t:"غذاسنجِ پیشی", back:true},
 {k:"meter", big:"~۱۱ روز", band:"بازهٔ ۹ تا ۱۳ روز", conf:"اطمینان: متوسط", src:"آخرین تأیید شما: ۶ روز پیش", cta:""},
 {k:"kv", t:"مبنای این تخمین", rows:[["کیسه","باز شده ۳ تیر — ثبت‌شده ●"],["سهم پیشی","حدود دوسوم — گفتهٔ شما"],["ترکیب","بیشتر خشک — گفتهٔ شما"],["اصلاح‌ها","۲ بار — بازه را باریک کرده"]]},
 {k:"pills", cols:2, opts:[{t:"▮▮▮▮ پر"},{t:"▮▮▮▯ بیش از نصف"},{t:"▮▮▯▯ کمتر از نصف"},{t:"▮▯▯▯ ته کیسه"}]},
 {k:"note", t:"اصلاحِ شما همین حالا اعمال می‌شود و نرخ مصرف برای کیسه‌های بعدی یاد گرفته می‌شود."}]},
{id:"C6", label:"EXTERNAL PURCHASE — FIRST-CLASS", note:"Outside purchases enter the same inventory; no sulking, meter continues.", blocks:[
 {k:"appbar", t:"افزودن غذای دیگر", back:true},
 {k:"input", label:"نام یا برند", val:"غذای خشک مرغ — خرید حضوری"},
 {k:"pills", opts:[{t:"۱ کیلو"},{t:"۲ کیلو", on:true},{t:"دیگر"}]},
 {k:"pills", opts:[{t:"برای پیشی"},{t:"مشترک"},{t:"فقط موجودی خانه"}]},
 {k:"btn", t:"افزودن به انبار خانه", kind:"primary"},
 {k:"note", t:"غذاسنج با همین کیسه ادامه می‌دهد — فرقی نمی‌کند از کجا خریده‌اید."}]}
]},

{id:"D", title:"Reorder — outcome-first", intent:"Trigger: pessimistic remaining vs offer-specific promise + buffer. Consequence leads; arithmetic behind «چطور محاسبه شد؟». Dismissal, external purchase and unavailability are first-class.", screens:[
{id:"D1", label:"REORDER CARD IN TODAY", note:"Max one card; outcome sentence first (Gate 2.1 §6).", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"warn", t:"در سناریوی کندتر، غذا ممکن است پیش از رسیدن کیسهٔ جدید تمام شود", tone:"warm"},
 {k:"kv", rows:[["غذای باقی‌مانده","~۱۶ تا ۲۱ روز · تخمینی"],["تحویل این پیشنهاد","۷ تا ۱۲ روز + حاشیهٔ اطمینان"]]},
 {k:"btn", t:"دیدن گزینه‌ها", kind:"primary"},
 {k:"btn", t:"چطور محاسبه شد؟", kind:"text"},
 {k:"btn", t:"بعداً (تا ۳ روز)", kind:"quiet"},
 {k:"nav", a:0}]},
{id:"D2", label:"HOW CALCULATED — ON REQUEST", note:"The arithmetic never leads; it is an optional disclosure.", blocks:[
 {k:"appbar", t:"چطور محاسبه شد؟", back:true},
 {k:"kv", rows:[["بدبینانه‌ترین تخمین غذا","۱۶ روز"],["دیرترین تحویل وعده‌شده","۱۲ روز"],["حاشیهٔ اطمینان","۵ روز"]]},
 {k:"kv", rows:[["۱۶ − (۱۲ + ۵)","کمتر از صفر → پیشنهاد: سفارش در همین هفته"]]},
 {k:"note", t:"حاشیهٔ اطمینان از دادهٔ واقعی تأخیرها می‌آید و به‌مرور تنظیم می‌شود."}]},
{id:"D3", label:"OPTIONS — REASONS STATED", note:"«هم‌ردهٔ تغذیه‌ای» claims only with professional approval; until then the reason is speed/availability.", blocks:[
 {k:"appbar", t:"گزینه‌های سفارش", back:true},
 {k:"kv", t:"همان سالمون ۲ کیلوگرم", rows:[["قیمت","۲٬۴۸۰٬۰۰۰ تومان"],["تحویل","۷ تا ۱۲ روز"]]},
 {k:"btn", t:"سفارش همین", kind:"primary"},
 {k:"kv", t:"جایگزین: بوقلمون ۲ کیلوگرم", rows:[["قیمت","۲٬۲۹۰٬۰۰۰ تومان"],["تحویل","۵ تا ۹ روز · دلیل پیشنهاد: سریع‌تر"]]},
 {k:"btn", t:"جای دیگری خریدم", kind:"quiet"}]},
{id:"D4", label:"BOUGHT ELSEWHERE", note:"External bag becomes first-class inventory; meter continues.", blocks:[
 {k:"check", t:"خریدید؟ خوب است", sub:"مهم این است که غذای پیشی نمی‌رسد به ته"},
 {k:"btn", t:"افزودن به انبار خانه", kind:"primary"},
 {k:"note", t:"غذاسنج با همان کیسه ادامه می‌دهد و کارت سفارش ساکت می‌شود."}]},
{id:"D5", label:"UNAVAILABLE — HONEST", note:"Muted ink, never error red; notify + concierge; alternatives never auto-substituted.", blocks:[
 {k:"appbar", t:"سالمون ۲ کیلوگرم", back:true},
 {k:"badges", items:[{t:"○ موقتاً ناموجود", tone:"mute"}]},
 {k:"text", t:"در حال حاضر تأمین‌کنندهٔ تأییدشده‌ای در دسترس نیست. به‌محض فراهم شدن خبر می‌دهیم."},
 {k:"btn", t:"به من خبر بده", kind:"primary"},
 {k:"btn", t:"درخواست تأمین اختصاصی", kind:"brass"},
 {k:"kv", t:"جایگزین آمادهٔ سفارش", rows:[["بوقلمون ۲ کیلوگرم","۲٬۲۹۰٬۰۰۰ · تحویل ۵ تا ۹ روز"]]}]},
{id:"D6", label:"SNOOZED — QUIET", note:"Snooze respected; re-raises only on threshold change.", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},
 {k:"toast", t:"باشد — تا ۳ روز ساکت می‌مانیم، مگر تخمین بدتر شود"},
 {k:"meter", big:"~۱۸ روز", band:"بازهٔ ۱۶ تا ۲۱ روز", conf:"اطمینان: متوسط", src:"سالمون ۲ کیلو", cta:""},
 {k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"", water:true},
 {k:"nav", a:0}]}
]},

{id:"E", title:"Care journey — approved content only", intent:"Offered, never auto-started, and only when professionally approved. Unapproved content = absence (no ratios, no Start, no pending badge). Stopping is a respected outcome.", screens:[
{id:"E1", label:"OFFER — ELIGIBILITY MET", note:"Appears only when blending is really possible. Research build: neutral content, no approval claim — the approved badge returns only with professional sign-off.", blocks:[
 {k:"appbar", t:"مسیر تغییر غذا"},
 {k:"note", t:"نسخهٔ پژوهشی — محتوای خنثی، بدون ادعای تأیید متخصص"},
 {k:"kv", rows:[["غذای جدید","بوقلمون — رسیده و باز نشده"],["غذای قبلی","حدود ۸ روز باقی‌مانده"],["نتیجه","شرط ترکیب تدریجی برقرار است"]]},
 {k:"btn", t:"بررسی مسیر ۱۴روزه", kind:"primary"},
 {k:"btn", t:"نه، ممنون", kind:"quiet"},
 {k:"note", t:"هرگز خودکار شروع نمی‌شود — فقط با تصمیم شما."}]},
{id:"E2", label:"PLAN REVIEW — APPROVED", note:"Research build: qualitative stages only — exact ratios enter the prototype exclusively after professional approval.", blocks:[
 {k:"appbar", t:"برنامهٔ ۱۴روزه", back:true},
 {k:"kv", rows:[["مرحلهٔ آغاز","بیشتر غذای قبلی، کمی جدید"],["مرحلهٔ میانی","ترکیب میانی"],["مرحلهٔ پایانی","کاملاً غذای جدید"]]},
 {k:"note", t:"نسبت‌های دقیق فقط پس از تأیید متخصص وارد می‌شود؛ برنامه بر اساس ~۸ روز غذای باقی‌ماندهٔ شما زمان‌بندی شده است."},
 {k:"btn", t:"شروع مسیر", kind:"primary"},
 {k:"btn", t:"نه حالا", kind:"quiet"}]},
{id:"E3", label:"CHECK-IN — NIGHT 6", note:"Check-ins exist only inside the journey window.", blocks:[
 {k:"appbar", t:"چک‌این شب ششم", back:true},
 {k:"title", t:"امشب چطور بود؟"},
 {k:"pills", opts:[{t:"خوب خورد"},{t:"کمتر خورد"},{t:"مشکلی بود"}]},
 {k:"text", t:"فقط در طول مسیر می‌پرسیم — نه همیشه.", dim:true}]},
{id:"E4", label:"EXCEPTION — NO DIAGNOSIS", note:"Escalation copy intentionally withheld until professional approval; structure only. Never a medical conclusion.", blocks:[
 {k:"warn", t:"باشد — یک قدم آرام‌تر می‌رویم", sub:"این تشخیص نیست — متن راهنمای تخصصی پس از تأیید اضافه می‌شود", tone:"warm"},
 {k:"pills", opts:[{t:"ادامهٔ آهسته"},{t:"مکث"},{t:"توقف کامل"}]},
 {k:"note", t:"هر سه انتخاب محترم است و تاریخچه در دفترچه می‌ماند."}]},
{id:"E5", label:"PAUSED / STOPPED — RESPECTED", note:"Stopping is a safe outcome, never framed as failure.", blocks:[
 {k:"appbar", t:"مسیر تغییر غذا", back:true},
 {k:"title", t:"مسیر متوقف شد", sub:"تاریخچه در دفترچهٔ پیشی ماند"},
 {k:"btn", t:"شروع دوباره — هر وقت خواستید", kind:"quiet"},
 {k:"btn", t:"بازگشت به امروز", kind:"quiet"}]},
{id:"E6", label:"COMPLETION → MEMORY → REVEAL", note:"= 3A-5. Preference saved only with explicit confirmation.", blocks:[
 {k:"appbar", t:"مسیر تغییر غذا", badge:{t:"✓ کامل شد", tone:"pos"}},
 {k:"kv", rows:[["مسیر ۱۴روزه","در عمل ۱۶ روز — با یک مکثِ شما"],["چک‌این‌ها","۱۲ از ۱۴ شب"],["خاطره","در دفترچه ثبت شد"]]},
 {k:"deep", t:"سروِ باغ آمادهٔ کاشت است", sub:"برای همیشه به همین خاطره پیوند دارد", pills:[{t:"قطعهٔ شمالی"},{t:"کنار حوض", on:true},{t:"گوشهٔ نهال‌ها"}]},
 {k:"kv", t:"بوقلمون به ترجیح‌های پیشی اضافه شود؟", rows:[["ذخیره","فقط با تأیید شما"]]},
 {k:"pills", opts:[{t:"بله، اضافه شود"},{t:"نه"}]}]},
{id:"E7", label:"DIARY — MEMORY DETAIL", note:"Durable record; the garden object links back here.", blocks:[
 {k:"appbar", t:"دفترچهٔ پیشی · آبان", back:true},
 {k:"kv", t:"تغییر غذا به بوقلمون", rows:[["بازه","۱۲ تا ۲۸ آبان ۱۴۰۵"],["روند","۱۶ روز، با یک مکث"],["شیء باغ","سرو — کنار حوض"]]},
 {k:"photo", h:110, cap:"memory photo (optional, owner-added)"},
 {k:"btn", t:"دیدن سرو در باغ", kind:"brass"}]}
]},

{id:"F", title:"Persian Garden — full state set", intent:"Eligibility-based milestone catalogue; one illustrative example, no schedule; alive during inactivity; explicit quadrant rule.", screens:[
{id:"F1", label:"FIRST VISIT — DAY 0", note:"Plot + faint چهارباغ plan + pet presence + exactly one dashed next slot.", dark:true, blocks:[
 {k:"gappbar", t:"باغِ پیشی", right:"۰ از ۷ جای‌گاه"},
 {k:"garden", v:"bare"},
 {k:"gslot", t:"جای بعدی: سنگفرش", sub:"با تکمیل پروفایل پیشی — دلیلِ هر گشایش همین‌جا نوشته می‌شود"},
 {k:"gtext", t:"این باغ با رسیدگیِ واقعی ساخته می‌شود — نه با خرید، نه با ضربه‌زدن."}]},
{id:"F2", label:"OBJECT REVEAL", note:"Sprout glow ≤1.2s (motion §5); reserved for real milestones only.", dark:true, blocks:[
 {k:"gappbar", t:"باغِ پیشی", right:""},
 {k:"garden", v:"reveal"},
 {k:"gslot", t:"سنگفرشِ مسیر آماده شد", sub:"از تکمیل پروفایل — خاطره‌اش در دفترچه ثبت شد"},
 {k:"btn", t:"کاشت در باغ", kind:"gold"}]},
{id:"F3", label:"PLACEMENT — OWNER AGENCY", note:"Drag or tap-to-place; removal → انبارک storage, never destroyed.", dark:true, blocks:[
 {k:"gappbar", t:"کجا بنشیند؟", right:""},
 {k:"garden", v:"est"},
 {k:"pills", opts:[{t:"قطعهٔ شمالی"},{t:"کنار حوض", on:true},{t:"گوشهٔ نهال‌ها"}], gold:true},
 {k:"gtext", t:"بعداً هم می‌توانید جابه‌جا کنید — یا در انبارک نگه دارید."}]},
{id:"F4", label:"ESTABLISHED — ~3 OBJECTS", note:"= 3A-4: object↔memory link, next slot with reason, explicit «۳ از ۷».", dark:true, blocks:[
 {k:"gappbar", t:"باغِ پیشی", right:"۳ از ۷ جای‌گاه"},
 {k:"garden", v:"est"},
 {k:"gobj", t:"این سرو — پایان مسیر تغییر غذا", sub:"آبان ۱۴۰۵ · ۱۶ روز، با یک مکث", cta:"دیدن خاطره"},
 {k:"gslot", t:"جای بعدی: بوته‌های گل", sub:"با پایان برنامهٔ سرگرمی پاییز — یا نقطهٔ عطف ثبت‌شدهٔ خودتان"}]},
{id:"F5", label:"MEMORY DETAIL — FROM OBJECT", note:"The garden is the diary, rendered emotionally.", dark:true, blocks:[
 {k:"gappbar", t:"خاطرهٔ سرو", right:""},
 {k:"gobj", t:"تغییر غذا به بوقلمون", sub:"آبان ۱۴۰۵ · مسیر ۱۴روزه، در عمل ۱۶ روز", cta:""},
 {k:"gtext", t:"«شب ششم کمتر خورد؛ آرام‌تر رفتیم و رسیدیم.» — یادداشت شما"},
 {k:"btn", t:"دیدن در دفترچه", kind:"gold"},
 {k:"btn", t:"بازگشت به باغ", kind:"gquiet"}]},
{id:"F6", label:"INACTIVITY RETURN — ALIVE", note:"No decay, no stopped water, no recovery task — a greeting only.", dark:true, blocks:[
 {k:"gappbar", t:"باغِ پیشی", right:"۳ از ۷ جای‌گاه"},
 {k:"garden", v:"est"},
 {k:"gslot", t:"خوش برگشتید — باغ منتظرتان بود", sub:"هیچ چیزی کم نشده و هیچ جبرانی لازم نیست"}]},
{id:"F7", label:"QUADRANT FULL → NEXT OPENS", note:"Visible rule: quadrant opens when its slots fill; no hidden XP. V1 ships this single unlock.", dark:true, blocks:[
 {k:"gappbar", t:"باغِ پیشی", right:"۷ از ۷ جای‌گاه"},
 {k:"garden", v:"full"},
 {k:"gslot", t:"قطعهٔ دومِ چهارباغ باز شد", sub:"چون هر ۷ جای‌گاهِ قطعهٔ اول پر شد + کارت خاطرهٔ «فصل اول»"},
 {k:"gtext", t:"اشیای قطعهٔ اول دست‌نخورده می‌مانند."}]}
]},

{id:"G", title:"Multi-pet & household inventory", intent:"Switching swaps the pet layer; the household layer persists. Bags belong to the household; consumption belongs to pets.", screens:[
{id:"G1", label:"TODAY — SWITCHED TO رکس", note:"Full pet-layer swap; shared bag names co-consumers; household layer identical.", blocks:[
 {k:"pets", list:[{n:"پیشی", sp:"cat"},{n:"رکس", sp:"dog", on:true}]},
 {k:"meter", big:"~۹ روز", band:"بازهٔ ۷ تا ۱۲ روز", conf:"اطمینان: متوسط", src:"کیسهٔ مشترک با پیشی — سهم رکس", cta:"جزئیات و اصلاح"},
 {k:"event", g:"pen", t:"دوشنبه — قطرهٔ ضدانگل رکس", sub:"ثبت‌شدهٔ شما"},
 {k:"gstrip", t:"باغِ رکس — خاکِ گرم‌تر، تازه شروع", sub:"جای بعدی: سنگفرش", water:false},
 {k:"nav", a:0}]},
{id:"G2", label:"HOUSEHOLD INVENTORY", note:"Open, unopened, external and deliberately-unassigned units are all legitimate.", blocks:[
 {k:"appbar", t:"انبار خانه"},
 {k:"kv", t:"سالمون ۲ کیلوگرم — باز", rows:[["مصرف","پیشی + رکس (مشترک)"],["باز شده","۳ تیر ۱۴۰۵"]]},
 {k:"kv", t:"بوقلمون ۲ کیلوگرم — نگشوده", rows:[["انتساب","پیشی"],["بدون تخمین","تا باز شدن"]]},
 {k:"kv", t:"غذای خشک مرغ — خرید بیرونی", rows:[["انتساب","ندارد — فقط موجودی خانه"]]},
 {k:"btn", t:"افزودن غذای دیگر", kind:"brass"},
 {k:"nav", a:1}]},
{id:"G3", label:"SHARES — UNKNOWN SCENARIO", note:"Household-level estimate with striped band; per-pet numbers hidden until shares exist.", blocks:[
 {k:"appbar", t:"کیسهٔ مشترک — سهم‌ها", back:true},
 {k:"pills", opts:[{t:"سهم هر کدام را می‌گویم"},{t:"حدودی"},{t:"نمی‌دانم", on:true}]},
 {k:"band", label:"تخمین در سطح خانه", right:"۶ تا ۱۶ روز", from:20, w:46, striped:true},
 {k:"note", t:"تا وقتی سهم‌ها نامشخص است، عددِ به‌تفکیکِ هر حیوان نمایش داده نمی‌شود — دقتِ ساختگی نداریم."}]}
]},

{id:"S", title:"سفر سفارش — factual statuses", intent:"Facts with dates; atmosphere only frames. Delivery hands off to inventory. Cancellation / failure / refund / replacement states await Product/Ops — kept out of production screens.", screens:[
{id:"S1", label:"NORMAL — IN TRANSIT", note:"Dawn band is the only atmosphere; every status is a timestamped ● event.", dawn:true, blocks:[
 {k:"appbar", t:"سفر سفارش", sub:"#۱۴۰۵-۰۷۳۲"},
 {k:"badges", items:[{t:"برنامه‌ریزی‌شده برای پیشی · قابل تغییر", tone:"line"}]},
 {k:"kv", rows:[["وضعیت","◐ در مسیر بین‌المللی"],["سررسید تحویل","۲۷ تیر ۱۴۰۵"],["لغو رایگان","پایان‌یافته — تأمین آغاز شده"]]},
 {k:"timeline", items:[{s:"done", t:"پرداخت تأیید شد", sub:"۱۳ تیر، ۱۸:۴۲"},{s:"done", t:"تأمین آغاز شد", sub:"۱۴ تیر، ۱۰:۰۵ — پایان لغو رایگان"},{s:"now", t:"در مسیر بین‌المللی", sub:"۱۶ تیر، ۰۹:۳۰ · انقضای دقیق ثبت شد: ۱۲ اسفند"},{s:"wait", t:"گمرک، بازرسی و تحویل", sub:"در انتظار"}]},
 {k:"note", t:"پس از تحویل، بسته به انبار خانه می‌رود — نگشوده، بدون تخمین مصرف."}]},
{id:"S2", label:"DELAYED — CONFIRMED FACTS ONLY", note:"⚠ INTERNAL: a reserved slot exists here for delay compensation, shipped disabled — customers see nothing about it until Product/Ops approves the policy. Only confirmed dates render.", sheet:true, blocks:[
 {k:"warn", t:"سفارش شما دیرتر می‌رسد", sub:"حمل بین‌المللی بیش از برآورد طول کشیده؛ تأمین ادامه دارد و سفارش لغو نشده است", tone:"warm"},
 {k:"kv", rows:[["سررسید اولیه","۲۷ تیر — گذشته"],["برآورد جدید","۳ مرداد ۱۴۰۵"]]},
 {k:"btn", t:"متوجه شدم", kind:"primary"},
 {k:"btn", t:"گفت‌وگو با پشتیبانی", kind:"quiet"}]},
{id:"S3", label:"DELIVERED → INVENTORY", note:"Handoff: unopened, no estimate; Flow C takes over from here.", blocks:[
 {k:"check", t:"تحویل شد", sub:"۲۵ تیر، ۱۱:۱۰ — دو روز زودتر از سررسید"},
 {k:"kv", rows:[["انبار خانه","سالمون ۲ کیلوگرم — نگشوده"],["تخمین مصرف","شروع نشده — تا باز شدن کیسه"]]},
 {k:"pills", opts:[{t:"انتساب به پیشی", on:true},{t:"مشترک"},{t:"بعداً"}]},
 {k:"btn", t:"کیسه را باز کردم — شروع راه‌اندازی", kind:"primary"}]}
]}
],

proto: {
happy: [
 {label:"PRODUCT", flow:"A", blocks:[{k:"appbar", t:"غذای خشک گربه", back:true},{k:"photo", h:120, cap:"product photo"},{k:"badges", items:[{t:"● آمادهٔ سفارش", tone:"pos"},{t:"اصالت: تأییدشده توسط تأمین‌کننده", tone:"pos"}]},{k:"title", t:"سالمون ۲ کیلوگرم — ۲٬۴۸۰٬۰۰۰ تومان"},{k:"kv", rows:[["تحویل","حداکثر ۱۴ روز"],["صرفه‌جویی","۳۶٪ نسبت به قیمت مرجع"],["بازبینی مرجع","۱۲ تیر ۱۴۰۵"]]},{k:"btn", t:"خرید و پرداخت", kind:"primary", tap:1}]},
 {label:"ORDER PLACED", flow:"A", blocks:[{k:"check", t:"پرداخت انجام شد", sub:"#۱۴۰۵-۰۷۳۲ · سررسید ۲۷ تیر"},{k:"text", t:"این غذا برای کیست؟ (برنامه‌ریزی اختیاری)"},{k:"pills", opts:[{t:"پیشی", tap:2},{t:"فعلاً هیچ‌کدام", tap:2}]}]},
 {label:"TODAY — INCOMING", flow:"B", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"food", tone:"info", badge:"◐ در راه", t:"سالمون ۲ کیلوگرم", sub:"در حال تأمین · تحویل ۲۷ تیر", rows:[], foot:"تخمین روزها پس از باز شدن کیسه", cta:""},{k:"btn", t:"دیدن سفر سفارش", kind:"brass", tap:3},{k:"gstrip", t:"باغِ پیشی — زمین آماده", sub:"", water:false},{k:"nav", a:0}]},
 {label:"سفر سفارش", flow:"S", blocks:[{k:"appbar", t:"سفر سفارش", sub:"#۱۴۰۵-۰۷۳۲"},{k:"timeline", items:[{s:"done", t:"پرداخت تأیید شد", sub:"۱۳ تیر"},{s:"done", t:"تأمین آغاز شد", sub:"۱۴ تیر"},{s:"now", t:"در مسیر بین‌المللی", sub:"۱۶ تیر"},{s:"wait", t:"تحویل", sub:"سررسید ۲۷ تیر"}]},{k:"btn", t:"شبیه‌سازی: تحویل شد", kind:"primary", tap:4},{k:"btn", t:"بازگشت به امروز", kind:"quiet", tap:2}]},
 {label:"DELIVERED → SETUP", flow:"S", blocks:[{k:"check", t:"تحویل شد", sub:"به انبار خانه — نگشوده"},{k:"text", t:"کیسه را باز کردید؟ روزی چقدر می‌خورد؟"},{k:"pills", opts:[{t:"باز شد — سهم را می‌گویم", tap:5},{t:"باز شد — نمی‌دانم", tap:8}]},{k:"btn", t:"هنوز نه — نگشوده بماند", kind:"quiet", tap:2}]},
 {label:"TODAY — ACTIVE", flow:"B", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"meter", big:"~۲۸ روز", band:"بازهٔ ۲۲ تا ۳۴ روز", conf:"اطمینان: متوسط", src:"باز شده امروز — گفتهٔ شما", cta:""},{k:"btn", t:"جزئیات غذاسنج", kind:"brass", tap:6},{k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"", water:true},{k:"nav", a:0}]},
 {label:"METER — CORRECTION", flow:"C", blocks:[{k:"appbar", t:"غذاسنجِ پیشی", back:true},{k:"meter", big:"~۲۸ روز", band:"۲۲ تا ۳۴ روز", conf:"اطمینان: متوسط", src:"۰ اصلاح", cta:""},{k:"text", t:"به‌نظرتان درست نیست؟"},{k:"pills", cols:2, opts:[{t:"▮▮▮▮ پر", tap:7},{t:"▮▮▮▯ بیش از نصف", tap:7},{t:"▮▮▯▯ کمتر از نصف", tap:7},{t:"▮▯▯▯ ته کیسه", tap:7}]},{k:"btn", t:"بازگشت", kind:"quiet", tap:5}]},
 {label:"CALM END", flow:"B", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"toast", t:"بازتنظیم شد — نرخ مصرف یاد گرفته شد"},{k:"meter", big:"~۲۴ روز", band:"بازهٔ ۲۲ تا ۲۷ روز — باریک‌تر", conf:"اطمینان: بالا", src:"اصلاحِ شما", cta:""},{k:"text", t:"امروز دیگر هیچ کاری لازم نیست.", dim:true},{k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"", water:true},{k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},{k:"nav", a:0}]},
 {label:"UNKNOWN — HOUSEHOLD-LEVEL BAND", flow:"C", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"band", label:"تخمین در سطح خانه — سهم‌ها نامشخص", right:"۱۸ تا ۴۲ روز", from:12, w:58, striped:true},{k:"text", t:"چون «نمی‌دانم» گفتید، عددِ به‌تفکیک پیشی نمایش داده نمی‌شود — بازه صادقانه پهن است.", dim:true},{k:"btn", t:"سهم را می‌گویم — بازه باریک شود", kind:"brass", tap:5},{k:"gstrip", t:"باغِ پیشی — آب روان است", sub:"", water:true},{k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},{k:"nav", a:0}]}
],
exception: [
 {label:"REORDER — OUTCOME FIRST", flow:"D", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"warn", t:"در سناریوی کندتر، غذا ممکن است پیش از رسیدن کیسهٔ جدید تمام شود", tone:"warm"},{k:"kv", rows:[["باقی‌مانده","~۱۶ تا ۲۱ روز"],["تحویل این پیشنهاد","۷ تا ۱۲ روز + اطمینان"]]},{k:"btn", t:"دیدن گزینه‌ها", kind:"primary", tap:2},{k:"btn", t:"چطور محاسبه شد؟", kind:"text", tap:1},{k:"nav", a:0}]},
 {label:"HOW CALCULATED", flow:"D", blocks:[{k:"appbar", t:"چطور محاسبه شد؟", back:true},{k:"kv", rows:[["بدبینانه‌ترین تخمین","۱۶ روز"],["دیرترین تحویل","۱۲ روز"],["حاشیهٔ اطمینان","۵ روز"],["نتیجه","کمتر از صفر → همین هفته"]]},{k:"btn", t:"بازگشت", kind:"quiet", tap:0}]},
 {label:"OPTIONS → UNAVAILABLE", flow:"D", blocks:[{k:"appbar", t:"گزینه‌ها", back:true},{k:"badges", items:[{t:"○ سالمون موقتاً ناموجود", tone:"mute"}]},{k:"btn", t:"به من خبر بده", kind:"primary", tap:3},{k:"kv", t:"جایگزین: بوقلمون", rows:[["تحویل","۵ تا ۹ روز · دلیل: سریع‌تر"]]},{k:"btn", t:"جای دیگری خریدم", kind:"quiet", tap:4}]},
 {label:"NOTIFY SET → QUIET TODAY", flow:"B", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"toast", t:"ثبت شد ✓ — به‌محض موجود شدن خبر می‌دهیم"},{k:"meter", big:"~۱۸ روز", band:"بازهٔ ۱۶ تا ۲۱ روز", conf:"اطمینان: متوسط", src:"سالمون ۲ کیلو", cta:""},{k:"text", t:"هیچ سفارشی ساخته نشد — فقط یک اعلان.", dim:true},{k:"gstrip", t:"باغِ پیشی — آرام", sub:"", water:true},{k:"btn", t:"شبیه‌سازی: سفارشِ در راه دیرتر می‌رسد", kind:"quiet", tap:5},{k:"btn", t:"جای دیگری خریدم", kind:"quiet", tap:4},{k:"nav", a:0}]},
 {label:"BOUGHT ELSEWHERE", flow:"D", blocks:[{k:"check", t:"خریدید؟ خوب است"},{k:"btn", t:"افزودن به انبار خانه", kind:"primary", tap:6},{k:"note", t:"غذاسنج با همان کیسه ادامه می‌دهد."}]},
 {label:"DELAYED — CONFIRMED FACTS ONLY", flow:"S", blocks:[{k:"warn", t:"سفارش شما دیرتر می‌رسد", sub:"تأمین ادامه دارد و سفارش لغو نشده است", tone:"warm"},{k:"kv", rows:[["سررسید اولیه","۲۷ تیر — گذشته"],["برآورد جدید","۳ مرداد ۱۴۰۵"]]},{k:"btn", t:"متوجه شدم", kind:"primary", tap:6},{k:"btn", t:"گفت‌وگو با پشتیبانی", kind:"quiet", tap:6}]},
 {label:"TODAY — SETTLED", flow:"B", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"meter", big:"~۱۹ روز", band:"بازهٔ ۱۶ تا ۲۲ روز", conf:"اطمینان: متوسط", src:"کیسهٔ جدید در انبار", cta:""},{k:"text", t:"وضعیت روشن ماند و تصمیم با شما بود — بدون بحران.", dim:true},{k:"gstrip", t:"باغِ پیشی — آرام", sub:"", water:true},{k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},{k:"nav", a:0}]}
],
garden: [
 {label:"CHECK-IN — LAST NIGHT", flow:"E", blocks:[{k:"appbar", t:"چک‌این شب چهاردهم", back:true},{k:"title", t:"امشب چطور بود؟"},{k:"pills", opts:[{t:"خوب خورد", tap:1},{t:"کمتر خورد", tap:1}]},{k:"text", t:"شب آخرِ مسیر", dim:true}]},
 {label:"COMPLETION → REVEAL", flow:"E", blocks:[{k:"appbar", t:"مسیر تغییر غذا", badge:{t:"✓ کامل شد", tone:"pos"}},{k:"kv", rows:[["۱۴ شب","در عمل ۱۶ روز"],["خاطره","در دفترچه ثبت شد"]]},{k:"deep", t:"سروِ باغ آمادهٔ کاشت است", sub:"", pills:[{t:"قطعهٔ شمالی", tap:2},{t:"کنار حوض", on:true, tap:2},{t:"گوشهٔ نهال‌ها", tap:2}]}]},
 {label:"GARDEN — PLANTED", flow:"F", dark:true, blocks:[{k:"gappbar", t:"باغِ پیشی", right:"۴ از ۷ جای‌گاه"},{k:"garden", v:"est"},{k:"gobj", t:"سرو نشست — کنار حوض", sub:"پیوند به خاطرهٔ مسیر", cta:""},{k:"btn", t:"دیدن خاطره", kind:"gold", tap:3},{k:"btn", t:"بازگشت به امروز", kind:"gquiet", tap:4}]},
 {label:"MEMORY DETAIL", flow:"F", dark:true, blocks:[{k:"gappbar", t:"خاطرهٔ سرو", right:""},{k:"gobj", t:"تغییر غذا به بوقلمون", sub:"آبان ۱۴۰۵ · ۱۶ روز، با یک مکث", cta:""},{k:"gtext", t:"«شب ششم کمتر خورد؛ آرام‌تر رفتیم و رسیدیم.»"},{k:"btn", t:"بازگشت به باغ", kind:"gquiet", tap:2}]},
 {label:"TODAY — CALM RETURN", flow:"B", blocks:[{k:"pets", list:[{n:"پیشی", sp:"cat", on:true},{n:"رکس", sp:"dog"}]},{k:"meter", big:"~۲۴ روز", band:"بازهٔ ۲۰ تا ۲۸ روز", conf:"اطمینان: بالا", src:"بوقلمون — غذای تأییدشدهٔ جدید", cta:""},{k:"gstrip", t:"سرو کنار حوض نشست", sub:"۴ از ۷ جای‌گاه", water:true},{k:"btn", t:"شروع دوباره", kind:"quiet", tap:0},{k:"nav", a:0}]}
]
}
};
