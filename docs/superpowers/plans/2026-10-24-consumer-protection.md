# خطة بناء منظومة حماية المستهلك

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** موقع واحد يستقبل شكوى حماية المستهلك من الويب أو تلغرام، ويتابعها حتى الإغلاق، مع أسعار ومعابر وتقارير، وجاهز للتشغيل المحلي والرفع على كوليفاي.

**Architecture:** جانغو يملك القواعد وواجهة JSON والويب هوك. React يتنقل بلا إعادة تحميل ويُجمع داخل صورة جانغو. PostgreSQL والملفات في volumes. رسائل تلغرام تُصف في قاعدة البيانات وتعاد حتى تنجح.

**Tech Stack:** Python 3.12، Django>=5.2,<5.3، Django REST Framework>=3.15,<4، PostgreSQL 16، Gunicorn، WhiteNoise، httpx، Pillow، React 18، TypeScript، Vite، Vitest، Playwright.

**Spec:** `docs/superpowers/specs/2026-10-24-consumer-protection-design.md`

**التنفيذ المختار:** وكيل تنفيذ بنموذج `gpt-5.6-terra-medium` ثم مراجعة بنموذج `claude-fable-5-1-thinking-high`. لا يُستبدل أي منهما بنموذج أضعف.

## Global Constraints

- الواجهة العربية واتجاه RTL للزائر والموظف.
- Python 3.12 وDjango 5.2 وDjango REST Framework. الواجهة React 18 مع TypeScript وVite داخل صورة جانغو.
- PostgreSQL 16.
- `docker-compose.yml` فيه `web` و`db` فقط. تلغرام ويب هوك على `web`.
- Volumes بالاسمين `media` و`pgdata`.
- الأسرار من البيئة. `.env` غير متتبَّع. `.env.example` كلمات مروره فارغة.
- توقيت التقارير `Asia/Hebron`. نهاية اليوم بداية اليوم التالي.
- الملف الأقصى 5 ميغابايت. صور الشكوى والأسعار والمعابر jpeg أو png أو webp. مرفقات الكشف jpeg أو png أو webp أو pdf، وبحد خمسة.
- كلمة المرور 12 محرفاً على الأقل. إعادة التعيين 16 محرفاً وتُعرض مرة واحدة.
- `DJANGO_DEBUG` افتراضياً متوقف، و`1` فقط عند طلبه.
- الحالات بالنص: `واردة`، `قيد المتابعة الميدانية`، `منتهية`، `قيد المتابعة في الشؤون القانونية`، `تم المعالجه خلص`.
- فشل الدخول: `بيانات الدخول غير صحيحة.`
- بعد تقديم الشكوى: `تم استلام الشكوى.` بلا رقم.
- تجاوز الحد: `تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً.`
- سباق القبول: `استلم هذه الشكوى مفتش آخر.`
- منع الصلاحية: `لا تملك صلاحية الوصول إلى هذه الصفحة.`
- غير المربوط في البوت: `هذا الحساب غير مربوط. اطلب رابط الربط من مدير النظام.`
- رد المواطن: `تم التعامل مع الشكوى تبعك: {العنوان}.`
- وصول شكوى: `وصلت شكوى في {المنطقة} بعنوان {العنوان}.`
- قبول المفتش: `قبل المفتش {الاسم} الشكوى وتوجه للمتابعة الميدانية.`
- الجغرافيا الأولى: `محافظة تجريبية`، `المنطقة الأولى`، `المنطقة الثانية`.
- عقد القائمة: `page` من 1، `page_size` الافتراضي 20 والحد 100، الرد `count` و`page` و`page_size` و`results`.
- لا لوحة جانغو الجاهزة واجهةً للمنتج، ولا دومين أمامي منفصل، ولا واتساب، ولا حساب زائر، ولا رقم تتبع.

## Review Focus

- مفتش ثانٍ يقبل الشكوى نفسها فيرى `استلم هذه الشكوى مفتش آخر.` ولا تتغير عن المفتش الأول.
- شكوى قُبلت وأُغلقت في يوم `Asia/Hebron` نفسه تُحسب منجزة ذلك اليوم ولا تُحسب معلقة في نهايته. الواردة بلا قبول لا تُحسب معلقة.
- تحديث تلغرام برقمه نفسه يعيد `200` ولا ينشئ شكوى ثانية ولا رسالة صف ثانية.
- فشل إرسال تلغرام يبقي الشكوى محفوظة ويبقي صف الإرسال بانتظار الإرسال.
- طلب مجهول لمسار ملف شكوى أو نشر قديم يُرفض، وآخر سعر عام يُخدم من مسار الأخير فقط.

## خريطة الملفات

- `config/` الإعدادات والمسارات وغلاف الصفحة الواحدة.
- `apps/geography/` محافظة ومنطقة.
- `apps/accounts/` المستخدم والدخول وbootstrap.
- `apps/complaints/` الشكوى والانتقالات والرؤية.
- `apps/publications/` الأسعار والمعابر.
- `apps/reports/` استعلامات التقارير.
- `apps/telegram/` الربط والويب هوك والصف.
- `apps/common/listing.py` عقد القوائم. `apps/common/files.py` فحص الملفات.
- `web/src/design-system/` المكوّنات الوحيدة للجداول والفلاتر.
- `web/src/pages/` الشاشات بلا وسم `table`.
- `web/e2e/` اختبارات المتصفح.
- `Dockerfile`، `docker-compose.yml`، `entrypoint.sh`، `.env.example`.

نداء تلغرام عبر `httpx` إلى `https://api.telegram.org`، بلا مكتبة بوت جاهزة. غلاف المتصفح ملف `index.html` المبني، وأي مسار غير `/api/` و`/health/` و`/static/` يعيده جانغو.

---

### Task 1: المشروع والصحة والحاوية

**Files:**
- Create: `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `manage.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `.env.example`, `.gitignore`
- Test: `apps/common/tests/test_health.py`

**Interfaces:**
- Consumes: لا شيء
- Produces: `GET /health/` يعيد `200` والنص `ok` إذا نجح `connection.ensure_connection()`، وإلا `503`. الإعدادات تقرأ المفاتيح من البيئة. `entrypoint.sh` في هذه المهمة يشغّل التهجير ثم `bootstrap` ثم Gunicorn. Task 18 تضيف تسجيل الويب هوك وحلقة الصف.

- [ ] **Step 1: Write the failing test**

```python
def test_health_ok_and_debug_defaults_off(self):
    response = self.client.get("/health/")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.content, b"ok")
    self.assertFalse(settings.DEBUG)
    self.assertEqual(settings.TIME_ZONE, "Asia/Hebron")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.common.tests.test_health --verbosity=1`
Expected: FAIL لأن المشروع غير موجود

- [ ] **Step 3: Implement the Django project, health view, and Docker stack**

`requirements.txt` يثبّت Django 5.2 وDRF وgunicorn وwhitenoise وpsycopg وPillow وhttpx. `Dockerfile` مرحلة Node ثم Python 3.12. `docker-compose.yml` خدمتا `web` و`db` على صورة `postgres:16`، والمنفذ `${PORT:-8000}`، والvolumes `media` و`pgdata`. `.env.example` فيه كل مفاتيح المواصفة وقيم كلمات المرور فارغة. `.gitignore` فيه `.env`. عند `BEHIND_PROXY=1` يُضبط `SECURE_PROXY_SSL_HEADER` على `HTTP_X_FORWARDED_PROTO`/`https` وملفات الارتباط الآمنة. `entrypoint.sh` هنا لا يستدعي تلغرام.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.common.tests.test_health --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config manage.py requirements.txt Dockerfile docker-compose.yml entrypoint.sh .env.example .gitignore apps/common
git commit -m "feat: add Django project, health check, and Coolify compose"
```

### Task 2: الجغرافيا

**Files:**
- Create: `apps/geography/models.py`, `apps/geography/services.py`, `apps/geography/api.py`
- Test: `apps/geography/tests/test_models.py`

**Interfaces:**
- Consumes: قاعدة Task 1
- Produces: `Governorate(name unique)` و`Region(governorate, name)` مع `UniqueConstraint` على `(governorate, name)`. `delete_governorate(pk) -> None` و`delete_region(pk) -> None` ترفضان برسالة `لا يمكن حذف سجل مرتبط.` إذا وُجد ابن أو شكوى أو مستخدم. `GET/POST /api/governorates/` و`/api/regions/` لمدير النظام فقط، وغيرهما `403`.

- [ ] **Step 1: Write the failing test**

```python
def test_duplicate_region_name_in_one_governorate_rejected(self):
    gov = Governorate.objects.create(name="محافظة تجريبية")
    Region.objects.create(governorate=gov, name="المنطقة الأولى")
    with self.assertRaises(IntegrityError):
        Region.objects.create(governorate=gov, name="المنطقة الأولى")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.geography.tests.test_models --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement the models and guarded delete**

رسالة الحذف المرفوض: `لا يمكن حذف سجل مرتبط.` تعديل الاسم مسموح.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.geography.tests.test_models --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/geography
git commit -m "feat: add governorates and regions"
```

### Task 3: الحسابات والدخول

**Files:**
- Create: `apps/accounts/models.py`, `apps/accounts/services.py`, `apps/accounts/api.py`
- Test: `apps/accounts/tests/test_auth.py`

**Interfaces:**
- Consumes: `Governorate`, `Region`
- Produces: `User` يرث `AbstractUser` مع `display_name` و`role` بقيم `admin` `governor` `inspector` `legal` و`governorate` و`region` و`can_publish_prices` و`can_publish_crossings` و`can_view_all_complaints`. `set_user_password(user, raw) -> None` يرفض أقل من 12. `POST /api/auth/login/` و`logout/` و`GET /api/auth/me/`.

- [ ] **Step 1: Write the failing test**

```python
def test_login_failure_is_generic_and_short_password_rejected(self):
    with self.assertRaises(ValidationError):
        set_user_password(user, "short-pass")
    response = self.client.post("/api/auth/login/", {"username": "missing", "password": "wrong-password-1"})
    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.json()["detail"], "بيانات الدخول غير صحيحة.")
```

وأضف اختباري الحساب المعطّل لا يدخل، و`PATCH` لا يغيّر `username`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.accounts.tests.test_auth --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement user rules and session login**

مدير النظام بلا محافظة ومنطقة. مدير المحافظة محافظة مطلوبة. المفتش محافظة ومنطقة تابعة لها. الشؤون القانونية بلا جغرافيا. الدخول بالجلسة وكعكة نفس الأصل.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.accounts.tests.test_auth --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/accounts
git commit -m "feat: add staff accounts and session login"
```

### Task 4: Bootstrap

**Files:**
- Create: `apps/accounts/management/commands/bootstrap.py`
- Test: `apps/accounts/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: نماذج Task 2 وTask 3
- Produces: أمر `bootstrap` آمن عند التكرار. ينشئ الجغرافيا التجريبية والحسابات الأربعة من البيئة فقط إذا غاب اسم المستخدم. لا يبدّل كلمة مرور موجودة.

- [ ] **Step 1: Write the failing test**

```python
def test_bootstrap_seeds_once_and_keeps_existing_password(self):
    call_command("bootstrap")
    call_command("bootstrap")
    self.assertEqual(Governorate.objects.filter(name="محافظة تجريبية").count(), 1)
    self.assertTrue(Region.objects.filter(name="المنطقة الأولى", governorate__name="محافظة تجريبية").exists())
    self.assertTrue(Region.objects.filter(name="المنطقة الثانية").exists())
    user = User.objects.get(username="inspector")
    user.set_password("changed-password-12")
    user.save()
    call_command("bootstrap")
    user.refresh_from_db()
    self.assertTrue(user.check_password("changed-password-12"))
```

وأضف اختبار كلمة أقصر من 12 توقف الأمر وتذكر اسم المفتاح، واختبار غياب `محافظة تجريبية` عند إنشاء المفتش يذكر الاسم الناقص.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.accounts.tests.test_bootstrap --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement `bootstrap`**

الاختبار يضبط أسماء المستخدمين `admin` و`governor` و`inspector` و`legal` وكلمات من 12 محرفاً على الأقل. المفاتيح المطلوبة هي مفاتيح المواصفة عدا مفاتيح تلغرام و`PORT`. `CSRF_TRUSTED_ORIGINS` مطلوب فقط عندما `BEHIND_PROXY=1`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.accounts.tests.test_bootstrap --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/management apps/accounts/tests/test_bootstrap.py
git commit -m "feat: bootstrap trial geography and staff accounts"
```

### Task 5: عقد القوائم

**Files:**
- Create: `apps/common/listing.py`
- Test: `apps/common/tests/test_listing.py`

**Interfaces:**
- Consumes: لا شيء من النطاق
- Produces: `paginate(queryset, params) -> dict` بالمفاتيح `count` `page` `page_size` `results`. `page_size` فوق 100 يُثبَّت عند 100. `ordering=-created_at` يعكس الترتيب.

- [ ] **Step 1: Write the failing test**

```python
def test_page_contract_caps_page_size(self):
    body = paginate(qs, {"page": "1", "page_size": "500", "ordering": "-created_at"})
    self.assertEqual(set(body), {"count", "page", "page_size", "results"})
    self.assertEqual(body["page_size"], 100)
    self.assertEqual(body["page"], 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.common.tests.test_listing --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement `paginate`**

أسماء الفلاتر المشتركة تبقى كما في المواصفة عند بناء الاستعلامات لاحقاً: `q` `status` `governorate` `region` `inspector` `date_from` `date_to` `role` `is_active`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.common.tests.test_listing --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/common/listing.py apps/common/tests/test_listing.py
git commit -m "feat: add the shared list contract"
```

### Task 6: نظام التصميم

**Files:**
- Create: `web/src/design-system/*`, `web/src/design-system/fonts/*`, `web/package.json`, `web/vite.config.ts`
- Test: `web/src/design-system/design-system.test.tsx`, `web/src/pages/no-table.test.ts`

**Interfaces:**
- Consumes: لا شيء من الخادم
- Produces: `FilterBar` و`DataTable` و`BulkActionBar` و`StatusChip` و`AppShell` و`Button` وحقول النص والقائمة والملف و`Timeline` وحالات الفراغ والتحميل والخطأ. الخط IBM Plex Sans Arabic من ملفات المستودع. الألوان `#f3efe6` `#1a1814` `#e2d9cc` `#1e4a38` `#9a4e2a` `#8c2f2a`.

- [ ] **Step 1: Write the failing test**

```tsx
it("renders the five status labels from one chip", () => {
  for (const label of ["واردة", "قيد المتابعة الميدانية", "منتهية", "قيد المتابعة في الشؤون القانونية", "تم المعالجه خلص"]) {
    render(<StatusChip status={label} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  }
})
```

وأضف اختباراً يفشل إذا وُجد وسم `table` داخل `web/src/pages`. `FilterBar` يقبل الأنواع: بحث، اختيار، تاريخ، مدى تاريخ. `DataTable` يخفي شريط الإجراء المجمّع عندما لا توجد إجراءات مجمّعة.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run` من مجلد `web`
Expected: FAIL

- [ ] **Step 3: Implement the design system**

الاتجاه `rtl`. الشريط الجانبي خلفية `#1a1814` ونص `#f3efe6` والبند الحالي `#1e4a38`. انحناء الحقول 6 والألواح 10. لا صفحة خارج النظام ترسم جدولاً أو شريط فلاتر.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run` من مجلد `web`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: add the Arabic design system"
```

### Task 7: غلاف الصفحة الواحدة والدخول

**Files:**
- Create: `web/src/main.tsx`, `web/src/router.tsx`, `web/src/pages/LoginPage.tsx`, `web/src/pages/AccountPage.tsx`, `config/spa.py`
- Modify: `config/urls.py`
- Test: `web/src/router.test.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/login/`، `GET /api/auth/me/`، مكوّنات Task 6
- Produces: مسارات المتصفح في المواصفة. `spa_shell(request) -> HttpResponse` يعيد `index.html` المبني. التنقل الداخلي لا يستدعي `location.reload`.

- [ ] **Step 1: Write the failing test**

```tsx
it("moves from complaints to account without a document navigation", async () => {
  render(<MemoryRouter initialEntries={["/complaints/"]}><App /></MemoryRouter>)
  await user.click(screen.getByRole("link", { name: "الإعدادات" }))
  expect(screen.getByRole("heading", { name: "الإعدادات" })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run src/router.test.tsx` من مجلد `web`
Expected: FAIL

- [ ] **Step 3: Implement the shell, login, and account settings**

الدخول الفاشل يعرض `بيانات الدخول غير صحيحة.` تغيير الاسم الظاهر وكلمة المرور يطلب الكلمة الحالية وطول 12 وتأكيداً مطابقاً. صفحة الدور الخطأ تعرض `لا تملك صلاحية الوصول إلى هذه الصفحة.` بنود الشريط حسب جدول المواصفة.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run src/router.test.tsx` من مجلد `web`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src config/spa.py config/urls.py
git commit -m "feat: add the single-page shell and account screens"
```

### Task 8: انتقالات الشكوى

**Files:**
- Create: `apps/complaints/models.py`, `apps/complaints/services.py`, `apps/common/files.py`
- Test: `apps/complaints/tests/test_transitions.py`

**Interfaces:**
- Consumes: `User`, `Governorate`, `Region`, `validate_upload(file, *, kinds: set[str]) -> None`
- Produces: `Complaint` و`FollowUp` و`FollowUpFile`. `accept_complaint` و`assign_complaint` و`submit_field_report` و`close_legal`. الحالات والنصوص كما في القيود العامة. سطر المتابعة لا يُحدَّث بعد الحفظ، ويحفظ `author_name` عند إنشائه.

- [ ] **Step 1: Write the failing test**

```python
def test_second_inspector_sees_taken_message(self):
    accept_complaint(complaint, inspector_a, channel="web", ip="10.0.0.1", telegram_id=None)
    with self.assertRaisesMessage(ValidationError, "استلم هذه الشكوى مفتش آخر."):
        accept_complaint(complaint, inspector_b, channel="web", ip="10.0.0.2", telegram_id=None)
    complaint.refresh_from_db()
    self.assertEqual(complaint.inspector_id, inspector_a.id)
```

وأضف اختبارات الانتقالات الخمس ورفض غيرها، ورفض كشف بلا نص، وقبول «تم الانجاز» بنص `تم الانجاز` عند غياب الملاحظات، ورفض ملف سادس أو أكبر من 5 ميغابايت أو نوع غير مسموح، ورفض تعديل سطر متابعة محفوظ.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.complaints.tests.test_transitions --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement the transition functions**

`accept_complaint` و`assign_complaint` يكتبان اسم المفتش ووقت القبول والقناة وعنوان IP للويب فقط، ولا ينشئان سطر متابعة. `submit_field_report(complaint, actor, text, files, destination)` حيث `destination` هو `governor` أو `legal`. التوجيه لمفتش مفعّل من محافظة الشكوى ومنطقتها فقط والشكوى `واردة`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.complaints.tests.test_transitions --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/complaints apps/common/files.py
git commit -m "feat: add complaint transitions"
```

### Task 9: رؤية الشكاوى وإجراءاتها

**Files:**
- Create: `apps/complaints/access.py`, `apps/complaints/api.py`
- Test: `apps/complaints/tests/test_access.py`

**Interfaces:**
- Consumes: دوال Task 8 و`paginate`
- Produces: `visible_complaints(user) -> QuerySet`. `POST /api/complaints/actions/` للأفعال `accept` `flag` `unflag`. أكثر من معرّف في `accept` يعيد `400`. الدور الذي لا يملك الفعل يعيد `403`.

- [ ] **Step 1: Write the failing test**

```python
def test_view_permission_is_read_only_and_accept_rejects_many_ids(self):
    self.assertTrue(visible_complaints(viewer_with_flag).filter(pk=other.id).exists())
    denied = self.client.post("/api/complaints/actions/", {"action": "accept", "ids": [other.id]}, content_type="application/json")
    self.assertEqual(denied.status_code, 403)
    many = self.client.post("/api/complaints/actions/", {"action": "accept", "ids": [1, 2]}, content_type="application/json")
    self.assertEqual(many.status_code, 400)
```

وأضف اختبارات قوائم المفتش ومدير المحافظة والشؤون القانونية ومدير النظام، وعلم المتابعة لمدير النظام ومدير المحافظة فقط.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.complaints.tests.test_access --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement access queries and the actions endpoint**

الرد `200` فيه `succeeded` و`failed`. القائمة من الأحدث `created_at`. فلاتر القائمة `status` ولمدير المحافظة ومدير النظام `region` أيضاً.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.complaints.tests.test_access --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/complaints/access.py apps/complaints/api.py apps/complaints/tests/test_access.py
git commit -m "feat: add complaint visibility and actions"
```

### Task 10: الملفات الخاصة والتوجيه والكشف

**Files:**
- Modify: `apps/complaints/api.py`, `config/urls.py`
- Test: `apps/complaints/tests/test_media.py`

**Interfaces:**
- Consumes: `visible_complaints`, دوال الانتقال
- Produces: `POST /api/complaints/<id>/assign/` و`field-report/` و`legal-close/`. `GET /api/media/complaints/<id>/` و`followups/<id>/<file_id>/` بعد فحص الرؤية. لا مسار `media` عام.

- [ ] **Step 1: Write the failing test**

```python
def test_anonymous_cannot_guess_a_complaint_file(self):
    response = self.client.get(f"/api/media/complaints/{complaint.id}/")
    self.assertIn(response.status_code, (401, 403, 404))
```

وأضف أن الرد القانوني الثاني يعيد `400` و`هذه الشكوى مغلقة.`

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.complaints.tests.test_media --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement guarded file routes and the single-item posts**

المرفق يُفتح فقط لمن يرى الشكوى. الرد القانوني الثاني يعيد `400` والنص `هذه الشكوى مغلقة.` خط التقدم في `GET /api/complaints/<id>/` يرتب السطور من الأقدم إلى الأحدث.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.complaints.tests.test_media apps.complaints.tests.test_transitions --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/complaints config/urls.py
git commit -m "feat: guard complaint files and single-item actions"
```

### Task 11: التقديم العام وحد المعدل

**Files:**
- Modify: `apps/complaints/api.py`, `apps/complaints/services.py`
- Test: `apps/complaints/tests/test_public.py`

**Interfaces:**
- Consumes: `validate_upload`, `Governorate`, `Region`
- Produces: `POST /api/complaints/public/`. النجاح `201` والجسم `{ "detail": "تم استلام الشكوى." }` بلا مفتاح رقم. الحد 10 لعناوين IP خلال ساعة متدحرجة.

- [ ] **Step 1: Write the failing test**

```python
def test_public_success_has_no_number_and_eleventh_is_rejected(self):
    ok = self.client.post("/api/complaints/public/", data)
    self.assertEqual(ok.status_code, 201)
    self.assertEqual(ok.json(), {"detail": "تم استلام الشكوى."})
    self.assertNotIn("id", ok.json())
    blocked = self.client.post("/api/complaints/public/", data)
    self.assertEqual(blocked.status_code, 429)
    self.assertEqual(blocked.json()["detail"], "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.complaints.tests.test_public --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement public create**

القناة `web` ويُحفظ IP. المنطقة يجب أن تتبع المحافظة. النموذج لا يعيد شكاوى أخرى.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.complaints.tests.test_public --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/complaints
git commit -m "feat: accept public complaints with a rate limit"
```

### Task 12: النشر

**Files:**
- Create: `apps/publications/models.py`, `apps/publications/api.py`
- Test: `apps/publications/tests/test_publications.py`

**Interfaces:**
- Consumes: `User`, `validate_upload`
- Produces: `PriceReport` و`CrossingReport`. `POST /api/prices/` و`POST /api/crossings/`. `GET /api/prices/latest/` و`GET /api/crossings/latest/` و`GET /api/media/prices/latest/` و`GET /api/media/crossings/latest/` للعامة. الجداول الكاملة لمدير النظام ولصاحب الصلاحية.

- [ ] **Step 1: Write the failing test**

```python
def test_public_latest_hides_older_rows_and_complaints(self):
    older = self.client.get("/api/prices/")
    self.assertEqual(older.status_code, 403)
    latest = self.client.get("/api/prices/latest/")
    self.assertEqual(latest.status_code, 200)
    self.assertNotIn("complaints", latest.json())
```

وأضف رفض عبور بلا نص ولا صورة، ورفض نشر بلا صلاحية حتى لمدير النظام، والسماح له بقراءة السطور.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.publications.tests.test_publications --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement publication rows**

كل حفظ سطر جديد وينسخ `publisher_name`. الفراغ العام: `لا توجد قائمة أسعار منشورة.` و`لا توجد حركة معابر منشورة.`

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.publications.tests.test_publications --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/publications
git commit -m "feat: publish price lists and crossing updates"
```

### Task 13: التقارير

**Files:**
- Create: `apps/reports/queries.py`, `apps/reports/api.py`
- Test: `apps/reports/tests/test_reports.py`

**Interfaces:**
- Consumes: `Complaint`, `FollowUp`, `PriceReport`, `CrossingReport`
- Produces: `governor_daily(governorate, day) -> dict` و`admin_report(params) -> dict`. `GET /api/governor/report/?date=` و`GET /api/reports/`.

- [ ] **Step 1: Write the failing test**

```python
def test_same_day_close_is_done_not_pending(self):
    report = governor_daily(gov, date(2026, 10, 24))
    self.assertEqual(report["done"], 1)
    self.assertEqual(report["pending"], 0)
    self.assertEqual(report["done_by_inspector"][inspector.display_name], 1)
```

وأضف شكوى ما زالت في الشؤون القانونية عند نهاية اليوم ضمن `pending`، وشكوى واردة بلا قبول خارج `pending`، ورفض `date_from` بعد `date_to` برسالة عربية، ومتوسط الزمن بالساعات والدقائق أو `null`، وبلوك النشر يتأثر بالتاريخ فقط.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.reports.tests.test_reports --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement the report queries**

اليوم الافتراضي هو اليوم في `Asia/Hebron`. فلتر الحالة يضيّق بلوك الشكاوى فقط. الأداء يستخدم المحافظة والمنطقة والمفتش والفترة. المسار لمدير المحافظة أو مدير النظام حسب الدور، وغيرهما `403`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.reports.tests.test_reports --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/reports
git commit -m "feat: add governor and admin reports"
```

### Task 14: إدارة المستخدمين

**Files:**
- Modify: `apps/accounts/api.py`, `apps/accounts/services.py`
- Test: `apps/accounts/tests/test_admin.py`

**Interfaces:**
- Consumes: `User`, `set_user_password`
- Produces: `POST /api/users/` و`PATCH /api/users/<id>/` و`POST /api/users/<id>/password/` و`DELETE /api/users/<id>/` و`POST /api/users/actions/` بـ `activate` و`deactivate`. `reset_password(user) -> str` طوله 16.

- [ ] **Step 1: Write the failing test**

```python
def test_reset_is_sixteen_chars_and_last_admin_cannot_be_deleted(self):
    raw = reset_password(inspector)
    self.assertEqual(len(raw), 16)
    self.assertTrue(inspector.check_password(raw))
    denied = self.client.delete(f"/api/users/{admin.id}/")
    self.assertEqual(denied.status_code, 400)
```

وأضف إلغاء جلسات المستخدم بعد تغيير كلمة المرور، وإبقاء `author_name` بعد حذف كاتب سطر متابعة، ورفض حذف النفس.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.accounts.tests.test_admin --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement user administration**

الحذف من مسار المفرد بعد تأكيد الواجهة، لا من الإجراء المجمّع. الاسم المنسوخ يُكتب عند إنشاء سطر المتابعة والنشر.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.accounts.tests.test_admin --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/accounts
git commit -m "feat: let the system admin manage users"
```

### Task 15: شاشات الموظفين والعامة

**Files:**
- Create: `web/src/pages/PublicPage.tsx`, `web/src/pages/ComplaintsPage.tsx`, `web/src/pages/ComplaintPage.tsx`, `web/src/pages/UsersPage.tsx`, `web/src/pages/GeographyPage.tsx`, `web/src/pages/ReportsPage.tsx`, `web/src/pages/PublicationsPage.tsx`
- Test: `web/src/pages/pages.test.tsx`

**Interfaces:**
- Consumes: عقد `/api/` ومكوّنات Task 6
- Produces: الشاشات في مسارات المواصفة. كل قائمة تمرر مخططها إلى `FilterBar` وصفوفها إلى `DataTable`.

- [ ] **Step 1: Write the failing test**

```tsx
it("submits a public complaint and shows the receipt without a number", async () => {
  render(<PublicPage />)
  await user.click(screen.getByRole("button", { name: "تقديم الشكوى" }))
  expect(await screen.findByText("تم استلام الشكوى.")).toBeInTheDocument()
  expect(screen.queryByText(/رقم/)).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run src/pages/pages.test.tsx` من مجلد `web`
Expected: FAIL

- [ ] **Step 3: Implement the screens**

بعد كل إجراء تُعاد قراءة البيانات بلا `location.reload`. الصفحة العامة ثلاثة أقسام بالفراغات المنصوصة. قائمة المفتش تعرض اسمه ومحافظته ومنطقته. تقرير المدير يستخدم حقل التاريخ من نظام التصميم. تقارير مدير النظام تستخدم `FilterBar`. الشاشات تستورد الجدول والفلاتر من `web/src/design-system` فقط.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run src/pages/pages.test.tsx` من مجلد `web`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/pages
git commit -m "feat: add public and staff screens"
```

### Task 16: اختبارات المتصفح للويب

**Files:**
- Create: `web/e2e/web.spec.ts`, `web/playwright.config.ts`
- Test: الأمر أدناه

**Interfaces:**
- Consumes: التطبيق الكامل حتى Task 15 و`bootstrap`
- Produces: سيناريوهات المتصفح لعمليات الويب في قسم اختبارات المواصفة، عدا صحة تلغرام التي تكملها Task 18.

- [ ] **Step 1: Write the failing test**

```ts
test("staff navigation does not add a document load", async ({ page }) => {
  await page.goto("/complaints/")
  const before = await page.evaluate(() => performance.getEntriesByType("navigation").length)
  await page.getByRole("link", { name: "الإعدادات" }).click()
  const after = await page.evaluate(() => performance.getEntriesByType("navigation").length)
  expect(after).toBe(before)
})
```

الملف نفسه يثبت النصوص: `تم استلام الشكوى.` و`تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً.` و`لا توجد قائمة أسعار منشورة.` و`بيانات الدخول غير صحيحة.` و`استلم هذه الشكوى مفتش آخر.` و`تم الانجاز` و`لا تملك صلاحية الوصول إلى هذه الصفحة.` مع القبول والتوجيه والإرسال للمدير وللشؤون القانونية وخط التقدم وعلامة المتابعة المفردة والمجمّعة والتقرير اليومي وفلاتر التقارير والنشر وتعديل الاسم وكلمة المرور وإنشاء الجغرافيا وإنشاء المستخدم وتعيين كلمة المرور وإعادة تعيينها وظهور 16 محرفاً مرة واحدة والحذف والتعطيل المجمّع.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run e2e` من مجلد `web`
Expected: FAIL قبل اكتمال الشاشات أو البيانات

- [ ] **Step 3: Point the flows at the running stack**

التشغيل عبر `docker compose up` ثم Playwright على `http://localhost:8000`. الحسابات من `.env` المحلي غير المتتبَّع.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run e2e` من مجلد `web`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/e2e web/playwright.config.ts
git commit -m "test: cover staff and public flows in the browser"
```

### Task 17: تلغرام

**Files:**
- Create: `apps/telegram/models.py`, `apps/telegram/outbox.py`, `apps/telegram/webhook.py`, `apps/telegram/links.py`, `apps/accounts/management/commands/send_telegram_outbox.py`
- Test: `apps/telegram/tests/test_webhook.py`

**Interfaces:**
- Consumes: دوال الشكاوى والنشر و`User`
- Produces: `POST /api/telegram/webhook/` معفى من CSRF ويفحص `X-Telegram-Bot-Api-Secret-Token`. `record_update(update_id: int) -> bool`. `enqueue(chat_id: int, text: str) -> TelegramOutbox`. `next_delay(attempts: int) -> timedelta` بالقيم 30 ثانية ثم دقيقتان ثم 10 دقائق ثم 30 دقيقة ثم كل 30 دقيقة. `create_staff_link(user) -> str`. `GET /api/telegram/health/` لمدير النظام.

- [ ] **Step 1: Write the failing test**

```python
def test_duplicate_update_and_failed_send_keep_one_complaint_and_the_outbox(self):
    first = self.client.post("/api/telegram/webhook/", update, **secret)
    second = self.client.post("/api/telegram/webhook/", update, **secret)
    self.assertEqual(first.status_code, 200)
    self.assertEqual(second.status_code, 200)
    self.assertEqual(Complaint.objects.count(), 1)
    self.assertEqual(TelegramOutbox.objects.filter(status="pending").count(), 1)
```

وأضف: سر خاطئ يعيد `403`؛ الشكوى لا تُنشأ قبل اكتمال المحافظة والمنطقة والعنوان والنص والإجابات الناقصة تبقى `TelegramDraft` لا `Complaint`؛ الصورة تُحفظ ملفاً محلياً والشكوى تبقى مربوطة بالمحافظة والمنطقة ثم بالمفتش عند القبول؛ الحد 10 لمعرّف تلغرام في الساعة؛ رسالة المواطن `تم التعامل مع الشكوى تبعك: عنوان المحل.`؛ التحويل القانوني لا يصف رسالة مواطن وتم الانجاز يصفها؛ شكوى الويب لا تُنشئ رسالة مواطن؛ أزرار الأسعار والمعابر ترسل آخر نشر أو فراغ المواصفة؛ مدير المحافظة يرى في البوت قوائم وصلت ومعلقة ومغلقة؛ الرمز يُربط مرة خلال 24 ساعة والرمز المستعمل يرفض؛ غير المربوط يرفض فعل الموظف بالنص المنصوص؛ المفتش المربوط يقبل عبر `accept_complaint`؛ فشل `setWebhook` على `{PUBLIC_BASE_URL}/api/telegram/webhook/` يكتب الحالة غير مسجّلة والموقع يستمر.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test apps.telegram.tests.test_webhook --verbosity=1`
Expected: FAIL

- [ ] **Step 3: Implement webhook, drafts, outbox, and staff linking**

`TelegramDraft` يحفظ خطوات البوت الناقصة ولا يظهر في القوائم. الأزرار العامة الثلاث بلا ربط. الموظف المربوط يراها مع أفعال دوره. إدارة المستخدمين وكلمات المرور لا تُنفَّذ من البوت. الإشعار يُدرج في الصف داخل معاملة حفظ الشكوى. `send_telegram_outbox` يرسل المستحق ولا يحذف الفاشل. رابط الربط `https://t.me/<username>?start=<token>` والبصمة فقط تُخزَّن. `GET /api/telegram/health/` يعيد حالة التسجيل وآخر خطأ ووقت آخر تحديث وعدد المنتظر وأقدم انتظار، ولغير مدير النظام `403`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test apps.telegram.tests.test_webhook --verbosity=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/telegram apps/accounts/management/commands/send_telegram_outbox.py
git commit -m "feat: add the Telegram webhook and outbox"
```

### Task 18: صحة تلغرام في الواجهة وإقلاع الحاوية

**Files:**
- Create: `web/src/pages/TelegramHealthPage.tsx`
- Modify: `entrypoint.sh`, `web/src/router.tsx`, `web/e2e/web.spec.ts`
- Test: `web/e2e/web.spec.ts`

**Interfaces:**
- Consumes: `GET /api/telegram/health/` وأمر `send_telegram_outbox`
- Produces: المسار `/telegram-health/` لمدير النظام فقط. الإقلاع يشغّل حلقة صف واحدة بجانب Gunicorn.

- [ ] **Step 1: Write the failing test**

```ts
test("system admin sees an unregistered webhook", async ({ page }) => {
  await page.goto("/telegram-health/")
  await expect(page.getByText("غير مسجّل")).toBeVisible()
})
```

وأضف أن المفتش على المسار نفسه يرى `لا تملك صلاحية الوصول إلى هذه الصفحة.`

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run e2e -- web.spec.ts` من مجلد `web`
Expected: FAIL

- [ ] **Step 3: Implement the health screen and the entrypoint processes**

الصفحة تعرض: مسجّل أو غير مسجّل، آخر خطأ، وقت آخر تحديث، عدد المنتظر، وأقدم وقت انتظار. `entrypoint.sh` لا يخرج إذا فشل تسجيل الويب هوك.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test && npm test -- --run && npm run e2e`
Expected: PASS من جذر المشروع ثم من `web`

- [ ] **Step 5: Commit**

```bash
git add web entrypoint.sh
git commit -m "feat: show Telegram health and keep the outbox running"
```
