# تقرير نقل مشروع CFOS (حتى 2026-11-21)

هذا التقرير يلخص كل ما أُنجز في المشروع وحالته الفعلية وما تبقى، ليستطيع أي حساب أو مساعد جديد متابعة العمل دون فقدان السياق. كل ما هو غير مُختبر على عتاد حقيقي موسوم بـ **[غير مُتحقق]**.

---

## 1. ما هو CFOS
نظام تشغيل Live مبني على **Debian 13 (Trixie) amd64** موجّه للفنيين (إصلاح الطابعات والأجهزة)، يتكوّن من:
- **صورة النظام** عبر Debian `live-build` (ISO هجين BIOS/UEFI).
- **CFOS Core**: حزمة Python (`cfos_core`) مع أمر `cfos` وخدمة مركزية عبر Unix socket، لإدارة أجهزة USB/PCI والتعريفات وتمرير USB إلى الآلات الافتراضية.
- واجهة مؤقتة: `labwc` + `greetd/tuigreet` + `waybar`. الواجهة النهائية (Qt 6/QML بتصميم زجاجي) **لم تبدأ**.

المبدأ الحاكم: النظام لا يثبّت تعريفات ولا يحمّل وحدات Kernel ولا ينزّل Firmware تلقائياً؛ كل إجراء مؤثر يحتاج موافقة صريحة وسجل تدقيق وإمكانية استرجاع.

## 2. بنية المشروع (جذر المستودع = مجلد `CFOS_Base_v0.1`)
```
auto/config                      إعداد lb config (التوزيعة، bootappend، الصورة)
config/package-lists/cfos-base.list.chroot   قائمة الحزم
config/hooks/normal/0100-cfos-base.hook.chroot  تفعيل الخدمات وchmod داخل الصورة
config/includes.chroot/          ملفات تُنسخ إلى الصورة:
   usr/bin/cfos, cfos-boot-report
   usr/lib/cfos/cfos_core/*.py   (نسخة منشورة من core/cfos_core، يجب أن تتطابق دائماً)
   usr/lib/systemd/system/cfos-core.service
   usr/lib/sysusers.d/cfos.conf  (مجموعة cfos)
   etc/greetd/config.toml, etc/labwc/environment, etc/skel/.config/labwc/*
   usr/share/cfos/build-info.txt, hardware-catalog.json
core/cfos_core/                  collector, daemon, cli, device_manager, udev_monitor,
                                 runtime_manager, hardware_profiles, driver_manager,
                                 install_manager, lifecycle
core/tests/                      57 اختباراً (unittest)
docs/                            ARCHITECTURE, BUILD, CORE_V0.2 … V0.8, PROJECT_STATUS_AND_REMAINING_PLAN
scripts/                         build-iso.sh, check-config.sh, check-packages.sh, clean-build.sh, test-iso-qemu.sh
tests/ACCEPTANCE.md              قوائم القبول على عتاد حقيقي
.github/workflows/build-iso.yml  البناء السحابي
```
**قاعدة مهمة:** بعد أي تعديل في `core/cfos_core` يجب نسخ الملفات إلى `config/includes.chroot/usr/lib/cfos/cfos_core/` والتأكد بـ `diff -rq`.

## 3. ما أُنجز في CFOS Core (الإصدار 0.8.0)
| الإصدار | المحتوى |
|---|---|
| 0.2–0.5 | معلومات الجلسة، CPU/RAM، CLI موحد، خدمة socket، حجوزات USB، سجل أحداث udev، تمرير USB عبر libvirt، تحليل الأجهزة |
| 0.6 / 0.6.1 | Driver Intelligence (قراءة فقط): ربط الجهاز بوحدات kernel وحزم Debian. **إصلاحان في 0.6.1**: انهيار `KeyError: 'function'` في ملخص PCI، وتقرير زائف `driver_bound` لأن `Path.resolve()` لا يفشل مع رابط `driver` غير موجود (استُبدل بـ `collector.bound_driver()`) |
| 0.7 | تثبيت التعريفات بموافقة: `driver-plan` (محاكاة `apt-get -s`) ثم `driver-apply` ثم `driver-rollback`. موافقة = تكرار plan id، يتطلب root و`--local`، صلاحية الخطة 15 دقيقة، إعادة محاكاة قبل التنفيذ، حجب الخطط التي تحذف حزماً أو تمس حزماً أساسية، سجل تدقيق `/var/log/cfos/audit.log` |
| 0.8 | دورة حياة USB: `usb-reconcile` (قراءة) و`usb-recover` (تحرير الحجوزات القديمة فقط)، تمرير دائم بمعرّفي vendor/product بدل bus/device، حماية من الفشل الجزئي لـ attach |

أوامر CLI الحالية: `status, resources, devices, sessions, events, reserve, release, passthrough, unpassthrough, hardware, profile, drivers, driver, driver-plan, driver-apply, driver-rollback, usb-reconcile, usb-recover`.

**حالة الاختبار:** 57 اختباراً ناجحاً، وكلها على محاكاة (mock). تجربة `virsh` وهمي مرّت. **لا شيء من منطق USB/الطابعات/libvirt/apt الحقيقي جُرّب على عتاد حقيقي [غير مُتحقق].**

## 4. مسار البناء (v0.9) — ما حدث فعلاً
- المستودع: `github.com/redacoman44-star/cfos` (جذر المستودع = محتويات `CFOS_Base_v0.1`).
- سير العمل `Build CFOS ISO` (يدوي `workflow_dispatch`) داخل حاوية `debian:trixie --privileged`: تثبيت الأدوات ← `check-packages.sh` ← `check-config.sh` + الاختبارات ← `build-iso.sh` ← `SHA256SUMS` ← رفع artifacts.
- تصحيحات تمت أثناء التجربة: حُذفت الحزمة `wayland` (ليست حزمة)، و`dnsutils` ← `bind9-dnsutils`، وأُضيف `python3` لأدوات الحاوية، وأُضيف `chmod 0755` للأمرين داخل الـ hook (الرفع من Windows يُفقد صلاحية التنفيذ).
- **النتيجة: البناء نجح.** الملف `live-image-amd64.hybrid.iso` ≈ 1.9 GB (+ `.contents` و`.packages` و`SHA256SUMS`).
- ملاحظة: ملاحظة Node.js 20 في Annotations تحذير غير مؤثر.
- معلومات الصورة المبنية: kernel 6.12.117-1، live-build 20250505+deb13u1، live-boot 1:20250815~deb13u1، live-config 11.0.5، Built 2026-11-21 11:47:18 UTC.

## 5. الاختبار على عتاد حقيقي
**الجهاز 1:** Pentium E5700، 4 GB RAM (لا VT-x غالباً)، أقلع بوضع BIOS من USB مكتوبة بـ Rufus (DD mode).
- ✔ ظهرت قائمة الإقلاع (isolinux) بخيارات: Live system، fail-safe، Start installer، Advanced install options، Utilities.
- ✔ أقلع النظام حتى شاشة نصية `tty1`.
- ✘ الشاشة: `Debian GNU/Linux 13 debian tty1` ثم `debian login: user (automatic login)` ثم **`Authentication failure`**. لم تظهر واجهة رسومية، ولم يستجب Alt+F2/F3.

**الجهاز 2:** Core i5-4440، 8 GB RAM (يدعم VT-x) — **لم يُختبر بعد**، وهو الخطوة التالية المباشرة (انظر §7).

## 6. المشاكل المفتوحة وتحليلها
1. **معاملات الإقلاع لم تُطبَّق (مؤكد من الصورة):** `username=cfos hostname=cfos` في `auto/config` لم تعمل؛ ظهر المستخدم `user` واسم الجهاز `debian`. الأرجح أن live-config 11 يتطلب الصيغة `live-config.username=` و`live-config.hostname=` و`live-config.locales=` و`live-config.keyboard-layouts=` **[الصيغة الصحيحة غير مُتحقق منها]**.
2. **`Authentication failure` عند الدخول التلقائي:** السبب غير معروف. فرضيات **[غير مُتحقق]**: (أ) تنافس `getty@tty1` (دخول live-config التلقائي) مع `greetd` على `vt = 1`، (ب) فشل `greetd`/`tuigreet` فتراجع النظام إلى getty، (ج) مشكلة PAM مع `login -f`.
3. **عدم استجابة Alt+F2/F3:** قد يكون تجمداً أو مشكلة كونسول؛ غير مفسَّر.
4. **`--debian-installer live`** في `auto/config` يضيف خيارات "Start installer" الخطرة على قرص الجهاز؛ قرار مفتوح: حذفه من الصورة.
5. **الرسوميات على بطاقة قديمة:** `WLR_RENDERER_ALLOW_SOFTWARE=1` أُضيف في `/etc/labwc/environment` وskel كاحتياط؛ تأثيره **[غير مُتحقق]**.

## 7. الخطوات التالية الموصى بها (بالترتيب)
1. **اختبار نفس الـ ISO على الجهاز i5-4440** (دون إعادة بناء): هل تظهر واجهة رسومية؟ إن فشل بالطريقة نفسها فالمشكلة في الإعدادات لا في العتاد. للتشخيص: في قائمة الإقلاع اضغط Tab وأضف `live-config.noautologin` لتظهر شاشة دخول عادية (`user` / `live` على الأرجح)، ثم `sudo cfos-boot-report` و`cat /tmp/cfos-boot-report-*.txt`.
2. **إصدار v0.9.1 مقترح (غير مُختبر):**
   - في `auto/config`: استبدال معاملات الإقلاع بـ `live-config.username=cfos live-config.hostname=cfos live-config.locales=en_US.UTF-8 live-config.keyboard-layouts=us` وإضافة `live-config.noautologin`، وإزالة `quiet splash` مؤقتاً لرؤية رسائل الإقلاع.
   - في `/etc/greetd/config.toml`: استخدام `[initial_session]` (command = labwc، user = cfos) مع بقاء `default_session` على tuigreet، بدل الاعتماد على دخول getty التلقائي.
   - اتخاذ قرار حذف `--debian-installer live`.
   - جعل `cfos-boot-report` يعمل تلقائياً ويحفظ التقرير في مكان يسهل الوصول إليه.
3. بعد الإقلاع السليم: تنفيذ قائمة `tests/ACCEPTANCE.md` (v0.6–v0.9) على العتاد، خصوصاً `cfos hardware/drivers/devices` وطابعة USB حقيقية وCUPS/SANE.
4. ثم المضي في الخطة: Resource Manager، Technician Center، ثم Shell (Qt 6/QML).

## 8. خريطة الطريق (من خطة المشروع الأصلية مع الحالة)
| الأولوية | الإصدار | المهمة | الحالة |
|---|---|---|---|
| P0 | 0.6.1 | إكمال التحقق وإعادة تغليف Driver Manager | ✔ |
| P0 | 0.7 | تثبيت التعريفات بموافقة الفني | ✔ (محاكاة فقط) |
| P0 | 0.8 | دورة حياة USB واستعادة الأجهزة | ✔ (محاكاة فقط) |
| P0 | 0.9 | بناء ISO واختبار الإقلاع | ISO بُني وأقلع حتى tty1؛ الدخول/الواجهة معطّلان |
| P1 | 1.0 | CFOS Shell (Qt 6/QML، تصميم زجاجي) | لم يبدأ |
| P1 | 1.1 | Technician Center | لم يبدأ |
| P1 | 1.2 | إدارة الطابعات والماسحات | لم يبدأ |
| P1 | 1.3 | Windows Runtime (Wine/Bottles، QEMU/KVM) | مخطط |
| P1 | 1.4 | Android 13 Runtime (Waydroid) | مخطط |
| P2 | 1.5–1.9 | تبديل إصدارات Android، Resource Manager (cgroups v2/zram)، Security & Update Manager (Polkit، تحديثات موقعة)، توسيع قاعدة التوافق، إصدار مستقر | لم يبدأ |

شروط إعلان الجاهزية: ISO ناجح على Debian 13، إقلاع UEFI وBIOS، اختبار USB/طابعات/ماسحات فعلياً، اختبار Windows VM وAndroid، استهلاك الذاكرة والمعالج، التحديث والاسترجاع، مراجعة الأمان، اعتماد التصميم الزجاجي.

## 9. كيف تتابع العمل من أي حساب
**تشغيل الاختبارات محلياً (Linux/Python 3):**
```
cd CFOS_Base_v0.1
PYTHONPATH=core python3 -m unittest discover -s core/tests
bash scripts/check-config.sh
PYTHONPATH=core python3 -m cfos_core.cli status --local
```
**البناء:** عدّل الملفات في المستودع ← Actions ← Build CFOS ISO ← Run workflow ← نزّل artifact `cfos-iso`. أي فشل: الصق آخر 30–50 سطراً من الخطوة الحمراء. قبل الرفع شغّل `scripts/check-packages.sh` إن كان لديك Debian 13.

**ملاحظات عن المستخدم والبيئة:**
- يتكلم العربية، وجهازه عليه Windows 10 بواجهة فرنسية؛ لا يوجد `winget`، وقد ثُبّت Git for Windows لدفع المشروع إلى GitHub.
- يفضّل خطوات صغيرة مرقمة وصوراً للشاشة بدل الأوصاف؛ الرفع عبر سحب الملفات في موقع GitHub **يسطّح المجلدات**، لذا يُستخدم `git push` أو تعديل ملف واحد من الموقع.
- يملك جهازين: Pentium E5700 + 4 GB (BIOS، بلا VT-x غالباً) وCore i5-4440 + 8 GB (يدعم VT-x، مناسب لاختبار KVM لاحقاً).
- الصلاحية على الملفات: الرفع من Windows يُسقط bit التنفيذ، لذلك يُعاد ضبطه في الـ hook وسكربتات البناء (`bash scripts/...`).

## 10. نص جاهز للصقه في المحادثة الجديدة
> أتابع مشروع CFOS: نظام Debian 13 live-build للفنيين مع حزمة Python اسمها cfos_core (الإصدار 0.8.0). أرفقت الحزمة `CFOS_Base_v0_9.zip` وتقرير النقل `CFOS_Handoff_Report.md`. حالة المشروع: الـ ISO بُني بنجاح عبر GitHub Actions وأقلع على جهاز Pentium E5700 حتى شاشة tty1، لكن الدخول التلقائي فشل (`Authentication failure`) والمستخدم/اسم الجهاز ظهرا `user/debian` بدل `cfos`، ولم تظهر الواجهة الرسومية. المطلوب: تشخيص المشكلة (ابدأ بنتيجة اختبار نفس الـ ISO على جهاز i5-4440) وإصدار v0.9.1 وفق §7 في التقرير. اشرح لي بالعربية وبخطوات صغيرة مرقمة.

---
*أُعدّ هذا التقرير بتاريخ 2026-11-21. الأجزاء الموسومة [غير مُتحقق] لم تُجرَّب على عتاد حقيقي.*
