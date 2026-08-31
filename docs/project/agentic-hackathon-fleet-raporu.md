# All Things Agentic Hackathon: Fortified Enterprise Fleet Raporu

Hazırlanma tarihi: 14 Ağustos 2026
Kaynak: Devpost yarışma sayfası (Overview, Rules, Resources, FAQ, Updates), Google Cloud ve ADK resmî dokümantasyonu, Google blog duyuruları.

Bu belge Faz 0 (yarışma sözleşmesini çözme) çıktısıdır. Fikir seçimi, kapsam kilidi ve mimari kararlar henüz alınmamıştır.

**Doğrulama durumu etiketleri:**
`[TEYİTLİ]` birincil kaynaktan doğrudan okundu.
`[ÇIKARIM]` kaynaklardan türetildi, doğrulanması gerek.
`[BELİRSİZ]` kaynaklar çelişiyor veya eksik, organizatöre sorulmalı.

---

## 1. Yarışma sözleşmesi

### 1.1 Kimlik ve yönetim

| Alan | Değer |
|---|---|
| Yarışma | All Things Agentic Hackathon |
| Sponsor | Google LLC |
| Yönetici (Administrator) | Devpost, Inc. |
| URL | https://allthingsagentichackathon.devpost.com/ |
| Challenge ID | 30845 |
| Toplam ödül havuzu | 180.000 USD |
| Katılımcı sayısı (14 Ağu itibarıyla) | ~2.400 ila 2.800 arası, sayfa yenilendikçe değişiyor |
| Uygulanacak hukuk | Kaliforniya eyalet hukuku, uyuşmazlıklar JAMS tahkimi (San Jose) |
| Yarışma yöneticisi e-posta | shawni@devpost.com |
| Google iletişim | cloudhackathons@google.com |

### 1.2 Uygunluk `[TEYİTLİ]`

- Bulunduğu ülkenin rüşt yaşının üzerinde olmak gerekiyor.
- **Türkiye hariç tutulan ülkeler listesinde değil.** Hariç tutulanlar: İtalya, Quebec, Kırım, Küba, İran, Suriye, Kuzey Kore, Sudan, Belarus, Rusya ve OFAC listesindeki diğer ülkeler.
- 3 Ağustos 2026 itibarıyla internet erişimi olması şartı var.
- Bir kamu kurumunda çalışanlar veya çıkar çatışması yaratacak durumdakiler uygun değil.
- Takım büyüklüğü sınırı yok. Tüm üyeler Devpost'ta projeye eklenmeli, bir kişi "Representative" olarak atanmalı, ödül ona ödenir ve paylaşımı o yapar.
- Bir kişi birden fazla proje gönderebilir, ancak her biri diğerlerinden esaslı biçimde farklı olmalı. Her proje en fazla bir ödül alabilir.

### 1.3 Takvim `[TEYİTLİ]`

| Aşama | Tarih |
|---|---|
| Başlangıç | 3 Ağustos 2026, 09:00 PT |
| Teslim son tarihi | 31 Ağustos 2026, 17:00 PT |
| Teslim son tarihi (Türkiye saati) | 1 Eylül 2026, 03:00 TRT `[ÇIKARIM]` PDT = UTC-7, TRT = UTC+3 |
| Kredi talep formu son tarihi | 28 Ağustos 2026, 12:00 PT (veya stok bitene kadar) |
| Jüri değerlendirmesi | 1 Eylül ila 1 Ekim 2026 |
| Kazananlar | 8 Ekim 2026 civarı |

Teslim süresi bittikten sonra submission üzerinde **hiçbir değişiklik yapılamaz**. FAQ ayrıca demo videosunu, repoyu ve canlı siteyi kazananlar açıklanana kadar olduğu gibi bırakmayı, geliştirmeye devam edilecekse repoyu fork'lamayı söylüyor.

### 1.4 Sıfırdan kod şartı `[TEYİTLİ]` KRİTİK

> "Projects must be newly created during the Submission Period."

- Proje 3 Ağustos ila 31 Ağustos arasında sıfırdan üretilmiş olmalı.
- Framework, kütüphane, starter template ve AI kodlama asistanları serbest.
- **Bunun dışındaki her önceden var olan kod veya çalışma açıkça beyan edilmek zorunda.**
- Pratik sonuç: mevcut AIstanbul kod tabanı olduğu gibi taşınamaz. Metodoloji, alan bilgisi ve veri taşınabilir; kod taşınacaksa beyan edilir.

### 1.5 Zorunlu teknoloji (her kategori için) `[TEYİTLİ]`

Üçü de zorunlu, hepsi aynı anda sağlanmalı:

1. **Gemini 3.5 veya daha yenisi**, Gemini API veya Vertex AI üzerinden erişilmiş olacak.
2. **En az bir Google agent framework'ü**: Google ADK, GenAI SDK, Antigravity SDK veya Genkit.
3. **En az bir Google Cloud altyapı servisi**: Cloud Run, Cloud SQL, Firestore, GKE, Pub/Sub gibi.

### 1.6 Teslim paketi `[TEYİTLİ]`

| Bileşen | Şart |
|---|---|
| Kategori | Tek kategori seçilir. Sponsor uygun görürse kategoriyi değiştirme hakkını saklı tutuyor. |
| Hosted proje URL'i | Varsa. "Highly encouraged" ama zorunlu değil. |
| Metin açıklaması | Özellikler, kullanılan teknolojiler, veri kaynakları, bulgular ve öğrenilenler. |
| Kod reposu | GitHub, GitLab veya Bitbucket. Private ise `testing@devpost.com` ve `cloudhackathons@google.com` erişimi verilmeli. |
| README spin-up talimatı | Adım adım kurulum/deploy. Jüri çalıştırmasa bile yeniden üretilebilirliğin kanıtı sayılıyor. |
| Mimari diyagram | Gemini'nin backend, veritabanı ve frontend ile nasıl bağlandığını gösteren görsel. |
| Demo videosu | En fazla 4 dakika. İlk 4 dakika değerlendirilir. YouTube veya Vimeo'da **herkese açık**. İngilizce veya İngilizce altyazılı. |

Video içeriği zorunlu olarak şunları içermeli:
- Çözülen problemin kısa tanımı
- Değer önerisi
- Uygulamanın çalışır hâlde demosu
- **Backend'in Google Cloud üzerinde çalıştığının kanıtı**: Cloud Console ekranı, Cloud Run dashboard, Vertex AI logları veya `.run` URL'inin tarayıcı adres çubuğunda görünmesi

Submission formunda ayrıca şu alanlar var (proje galerisi filtrelerinden görülüyor) `[TEYİTLİ]`:
- Submitter Type: Individuals / Team of individuals / Organization
- Startup Excellence ödülü için ayrı bir onay kutusu
- **"Did you add Reproducible Testing instructions to your README?" (Evet/Hayır)**

Son madde önemli: yeniden üretilebilirlik ayrı bir filtre alanı olarak var, yani jüri bunu ayrıca tarıyor.

### 1.7 Canlı olma şartı `[TEYİTLİ]`

Proje teslim veya jüri anında canlı olmak zorunda değil. Maliyeti sıfırlamak için servisler kapatılabilir. Ancak Google Cloud üzerinde inşa edildiğinin kanıtı opsiyonel değil. Kanıt videoda yakalanmalı, servisler kapatılmadan önce kaydedilmeli.

### 1.8 Ödül yapısı `[TEYİTLİ]`

| Ödül | Tutar | Adet |
|---|---|---|
| Grand Prize | 50.000 USD + 5.000 USD kredi | 1 |
| Taskmaster | 20.000 USD + 2.000 USD kredi | 1 |
| Collaborative Partner | 20.000 USD + 2.000 USD kredi | 1 |
| **Fortified Enterprise Fleet** | **20.000 USD + 2.000 USD kredi** | **1** |
| Startup Excellence | 20.000 USD + 5.000 USD kredi | 1 |
| Individual/Hobbyist (Best Team/Solo Build) | 10.000 USD + 1.000 USD kredi | 2 |
| Best Architectural Design | 5.000 USD + 1.000 USD kredi | 2 |
| Best Multimodal UX | 5.000 USD + 1.000 USD kredi | 2 |
| Honorable Mentions | 2.000 USD + 500 USD kredi | 5 |

Notlar:
- Grand Prize, tüm kategoriler arasında en yüksek puanı alan projeye gider.
- Bir proje en fazla bir ödül alabilir.
- Startup Excellence için tüzel kişilik ve kurumsal e-posta adresi gerekiyor. Şahıs olarak katılım bu ödüle uygun değil. `[TEYİTLİ]`
- **Individual/Hobbyist (2 kazanan) ve Best Architectural Design (2 kazanan), Fleet kategorisiyle aynı anda hedeflenebilir görünüyor** `[ÇIKARIM]`. Kurallar bunun nasıl çalıştığını açıkça yazmıyor, ancak "Top scoring projects in that judging criteria" ifadesi bunların kategoriden bağımsız verildiğini gösteriyor.

---

## 2. Puan bütçesi

Jüri iki (ödül bonusları sayılırsa üç) aşamada değerlendiriyor.

**Aşama 1 (Pass/Fail):** Submission tüm şartları içeriyor mu, bir kategoriye makul biçimde cevap veriyor mu, zorunlu teknolojiler makul biçimde uygulanmış mı.

**Aşama 2 (1 ila 5 puan, ağırlıklı):**

| Kriter | Ağırlık | Jürinin baktığı |
|---|---|---|
| Innovation & Operational Utility | %40 | Gerçek sürtünmeyi kendi başına ne kadar ortadan kaldırıyor. Otonom, yüksek değerli eylem; basit sohbet değil. |
| Architectural Discipline & Tech Stack | %30 | Sistemleri ayrıştırma, durum ve bellek yönetimi, kimlik bilgisi güvenliği, hata toleransı. Kırılgan script değil, üretim düşünülmüş agent. |
| Demo & Production Readiness | %30 | Videonun ve reponun çalıştığını kanıtlama netliği. Canlı, kurgusuz demo; temiz mimari diyagram; yeniden üretilebilir kurulum; Google Cloud kanıtı. |

**Aşama 3 (bonus, en fazla +1,0 puan):**

| Bonus | Puan |
|---|---|
| Nasıl inşa edildiğini anlatan içerik yayını (blog, podcast, video; herkese açık, unlisted değil, yarışma için üretildiği belirtilmeli) | +0,2 |
| Sosyal medya paylaşımı (X, LinkedIn, Instagram, Facebook; `#AllThingsAgenticHackathon` etiketiyle) | +0,2 |
| Ek Google AI modeli entegrasyonu (Gemma, Veo, Lyria), her biri +0,2, en fazla +0,6 | +0,6 |

Nihai puan 1 ila 6 arasında.

**Emek dağılımı kuralı:** Demo ve dokümantasyon toplam puanın %30'u. Yani emeğin de yaklaşık %30'u oraya gitmeli. Video geç kalınan iş değil, puanın üçte biri.

**Bonus puanların ağırlığı:** 1,0 bonus puan, 5 puanlık ölçekte %20'lik bir ek. Üç bonusun tamamı görece ucuz işlerle alınabilir. Bunları atlamak matematiksel olarak pahalı.

---

## 3. Fortified Enterprise Fleet: kategori beklentisi

### 3.1 Resmî tanım `[TEYİTLİ]`

> "Build a scalable network of institutional agents that hook into official enterprise infrastructure. Teams must demonstrate how agents are cataloged for cross-department use, how they safely maintain context across weeks of asynchronous operations, and how they interact with production data without violating enterprise compliance, data sovereignty, or security policies."

Bu cümlede üç zorunlu gösterim var:
1. Agent'ların departmanlar arası kullanım için **kataloglanması**
2. **Haftalar süren asenkron operasyonlar** boyunca bağlamın güvenle korunması
3. **Production veriyle**, uyum, veri egemenliği ve güvenlik politikalarını ihlal etmeden etkileşim

### 3.2 Resources sekmesindeki derinlemesine tanım `[TEYİTLİ]`

> "Corporate agent discovery, multi-agent orchestration at scale, long-term state persistence, runtime observability, and security posture enforcement. Show how an organization can discover your agents, audit their reasoning, trust their data handling, and scale them safely. Open to everyone, not just startups or enterprises."

Son cümle önemli: kategori herkese açık, kurumsal olmak şart değil.

### 3.3 Google'ın verdiği örnek `[TEYİTLİ]`

"Enterprise Supply Chain Orchestrator": bir satın alma müdürünün iç Agent Registry'de bulduğu, çok haftalı tedarikçi onboarding döngüsü yürüten agent. Teslimat webhook'larını izliyor, müzakere verisini Memory Bank'te hatırlıyor, özel ERP envanterini Agent Identity ile güvenli sorguluyor, lojistik alt agent'ıyla Agent Gateway üzerinden koordine oluyor, dış e-postaları Model Armor ile tarıyor.

**Klon riski uyarısı:** Bu, yarışmanın kendi verdiği örnek. Tedarik zinciri / satın alma orkestratörü fikri en yüksek klon riskini taşıyor. Aynı fikirle girmek ayırt edici bir açı olmadan puan kaybettirir.

### 3.4 Tavsiye edilen teknoloji: Gemini Enterprise Agent Platform (GEAP)

FAQ açıkça söylüyor `[TEYİTLİ]`:
> "These are recommended, not required, but they're what this track's judging is built around."

Yani teknik olarak zorunlu değiller, ama jüri kriteri bunların etrafında kurulmuş. Kullanmamak, %30'luk mimari kriterinde savunması zor bir tercih olur.

| Bileşen | Ne yapar | Fleet'te hangi cümleyi karşılar |
|---|---|---|
| **Agent Registry** | Agent, MCP server, tool, skill ve endpoint'lerin merkezi kataloğu. Yayınlama, versiyonlama, keşif. | "cataloged for cross-department use" |
| **Agent Runtime** | Uzun süreli, asenkron arka plan yürütme için yönetilen runtime. | "asynchronous operations" |
| **Memory Bank** | Oturumlar arası kalıcı, güvenli uzun vadeli bellek. | "maintain context across weeks" |
| **Agent Identity** | Her agent'a benzersiz kriptografik kimlik, sıfır güven erişim kontrolü, denetlenebilir iz. | "without violating security policies" |
| **Agent Gateway** | Agent ekosistemi için tek kontrol noktası, yönlendirme ve politika uygulama, Model Armor entegrasyonu. | "unified routing and policy enforcement" |
| **Model Armor** | Prompt injection, tool poisoning ve PII sızıntısına karşı satır içi guardrail. | "compliance, data sovereignty" |
| **Agent Observability** | OpenTelemetry uyumlu denetim logları ve uçtan uca akıl yürütme zinciri izleri. | "audit their reasoning" |

---

## 4. GEAP teknik notları

GEAP, Vertex AI'ın yerini alan platform. Duyuru: 22 Nisan 2026. Google'ın ifadesiyle "tüm Vertex AI servisleri ve yol haritası bundan sonra münhasıran Agent Platform üzerinden sunulacak."

### 4.1 Agent Runtime `[TEYİTLİ]`

- API'deki kaynak adı geriye dönük uyumluluk için hâlâ `ReasoningEngine`.
- Tam entegrasyon seviyesinde desteklenen tek framework **ADK**. LangChain, LangGraph, AG2, LlamaIndex "SDK entegrasyonu" seviyesinde; CrewAI ve özel framework'ler "custom template" seviyesinde.
- Günlerce otonom çalışan long-running agent desteği var (Nisan 2026 duyurusu).
- Ücretsiz katman mevcut.
- Deploy için **Agents CLI** (https://google.github.io/agents-cli/) var: hazır şablonlar (ReAct, RAG, multi-agent), interaktif playground, Terraform ile altyapı, Cloud Build CI/CD, Cloud Trace ve Cloud Logging.
- Bölge desteği ve kota sınırlıdır, deploy öncesi kontrol edilmeli.

### 4.2 Memory Bank `[TEYİTLİ]`

Yapı: her memory `{scope: {agent_name, user}, fact: "..."}` biçiminde bağımsız bir bilgi parçası.

Özellikler:
- **Memory extraction**: LLM ile konuşmadan anlamlı bilgi çıkarma
- **Memory consolidation**: yeni bilgiyi mevcut hafızayla birleştirme
- **Asenkron üretim**: arka planda memory üretme, agent beklemez
- **Sürekli event ingestion**: yapılandırılabilir batch kurallarıyla otomatik tetikleme
- **Özelleştirilebilir çıkarım**: topic ve few-shot örneklerle neyin anlamlı olduğunu tanımlama
- **Similarity search**: kimliğe kapsamlanmış benzerlik araması
- **TTL**: otomatik süre dolumu
- **Memory revisions**: hafızanın nasıl dönüştüğünü denetleme
- **IAM conditions**: hangi principal'ın hangi scope'u okuyup yazabileceğini kısıtlama
- ADK entegrasyonu: `VertexAiMemoryBankService`

**Governance bölümü, bu kategori için kritik `[TEYİTLİ]`:**

Dokümantasyon iki tehdidi açıkça adlandırıyor:
1. **Memory poisoning**: Memory Bank'e yanlış bilgi yazılması, agent'ın gelecekteki oturumlarda bu bilgiyle çalışması. Azaltma yolları: Model Armor ile prompt inceleme, adversarial test (red teaming), sandbox yürütme.
2. **Cross-border memory contamination**: bir yargı alanındaki (örneğin ABD) agent runtime veya service account'ın başka bir yargı alanındaki (örneğin AB) Memory Bank instance'ına yazması veya oradan okuması.

Önerilen kontroller: bölgeye özel agent identity / service account'lar, en az ayrıcalık rolleri (`roles/aiplatform.memoryViewer`, `roles/aiplatform.memoryEditor`), `gcp.resourceLocations` organizasyon politikası kısıtı, instance oluştururken bölgesel veya çok bölgeli konum seçimi (`eu`, `us`).

Bir uyarı da var: modelin bölgesel endpoint'i yoksa ML işleme global Gemini endpoint'lerine düşüyor. Gemini 3 modelleri bu örnek içinde açıkça sayılmış.

**Bu bölüm, "data sovereignty" jüri ifadesinin doğrudan teknik karşılığı. Fleet kategorisinde ayırt edici olmak isteyen bir proje bu kontrolleri gerçekten kuran ve gösteren proje olur.**

### 4.3 Model Armor `[TEYİTLİ]`

Filtreler:
- Responsible AI güvenlik kategorileri (nefret söylemi, taciz, cinsel içerik, tehlikeli içerik, şiddet, CSAM). CSAM varsayılan açık ve kapatılamaz.
- Prompt injection ve jailbreak tespiti (güven eşiği ayarlanabilir)
- Sensitive Data Protection (temel: kredi kartı, SSN, finansal hesap, ITIN, GCP credential, GCP API key; gelişmiş: SDP template'leri ile de-identification)
- Kötü amaçlı URL tespiti (ilk 40 URL taranıyor)

Uygulama tipi: `Inspect only` (sadece logla) veya `Inspect and block` (engelle). En iyi pratik: önce `Inspect only` ile blok oranını ölç, sonra `Inspect and block`'a geç.

Doküman tarama: PDF, CSV, TXT, DOCX, PPTX, XLSX. Girdi sınırı 4 MB.
Görsel tarama: Preview aşamasında, JPEG/PNG/BMP, 4 MB, sadece `us` ve `eu` çoklu bölgelerde.

**Kritik bulgu: dil desteği** `[TEYİTLİ]`

Responsible AI ve prompt injection / jailbreak filtreleri şu dillerde test edilmiş: Çince (Mandarin), İngilizce, Fransızca, Almanca, İtalyanca, Japonca, Korece, Portekizce, İspanyolca.

**Türkçe bu listede yok.** Doküman "diğer birçok dilde çalışabilir, ancak sonuç kalitesi değişebilir" diyor.

Bunun iki sonucu var:
- **Risk:** Türkçe içerikli bir kurumsal agent kurulursa, guardrail katmanının koruma gücü belgelenmemiş durumda. Bunu ölçmeden "korumalı" iddiasında bulunmak, Uydurma Yasağı'na girer.
- **Fırsat:** Ölçmek, güçlü ve nadir bir katkı olur. Türkçe prompt injection örnekleriyle Model Armor'ın tespit oranını ölçüp raporlamak, hem %40'lık inovasyon kriterine hem de bonus içerik yayınına doğrudan malzeme verir. Bu, Özge'nin dil ve mevzuat avantajının kod dışında da görünür olduğu tek nokta olabilir.

### 4.4 Agent Registry `[TEYİTLİ]`

Yönetilen kaynak tipleri: `Agent`, `McpServer`, `Endpoint`, `Skill`, `SkillRevision`, `Publisher`.

Yetenekler:
- Otomatik kayıt (desteklenen runtime'lardan) veya manuel kayıt (özel deployment'lar için)
- MCP server ve remote tool kaydı, orkestratörlere keşfedilebilir kılma
- Endpoint kaydı: agent'ların bağlanabileceği dış API ve servislerin merkezî yönetimi
- Anahtar kelime ve prefix araması
- Auth manager ve binding'lerle keşfedilen tool'lara güvenli kimlik doğrulama
- ADK entegrasyonu: dinamik endpoint çözümleme ve orkestratör agent kurma
- Kendi Agent Registry MCP server'ı var
- Denetim logları (audit logging) var

### 4.5 Agent Gateway ve Agent Identity `[TEYİTLİ]`

- Agent Identity her agent'a benzersiz kriptografik ID veriyor, her eylem yetkilendirme politikasına geri bağlanabilen denetlenebilir iz bırakıyor.
- Agent Gateway "hava trafik kontrolü" rolünde: agent'lar ve tool'lar arasında güvenli, birleşik bağlantı; tutarlı güvenlik politikası ve Model Armor korumasının uygulanması.
- Dört adet resmî codelab var (Agent Gateway ile yönetişim, Agent Runtime'dan Google MCP / harici MCP / VPC'ye egress). Bunlar en hızlı öğrenme yolu.
- Gateway için `gcloud network-services agent-gateways` CLI komutları mevcut.

### 4.6 Agent Observability `[TEYİTLİ]`

- OpenTelemetry uyumlu, Cloud Trace ve Cloud Logging tabanlı.
- Agent Runtime tarafında ayrı tracing, logging ve monitoring kurulum sayfaları var.
- Model Armor span'leri ayrıca görüntülenebiliyor.
- Semantic governance policy logları ve Agent Registry audit logları ayrı akışlar.

---

## 5. ADK 2.0

Kanonik adres artık **https://adk.dev** (google.github.io/adk-docs oraya yönlendiriyor).

Diller: Python, TypeScript, Go, Java, Kotlin. Kurulum: `pip install google-adk`.

ADK 2.0 ile gelen ve bu kategoriye doğrudan hizmet eden yetenekler:

| Yetenek | Doküman | Fleet'te işlevi |
|---|---|---|
| **Graph Workflows** | adk.dev/graphs/ | Deterministik kodu adaptif akıl yürütmeyle örme, açık yürütme yolları. Uyum akışlarında "her seferinde aynı yoldan geç" garantisi. |
| **Ambient Agents** | adk.dev/runtime/ambient-agents/ | Pub/Sub ve Eventarc trigger endpoint'leriyle olay tetiklemeli arka plan çalışması. |
| **Resume Agents** | adk.dev/runtime/resume/ | Çökme sonrası devam, uzun süreli iş akışları. |
| **Cancel Agent Runs** | adk.dev/runtime/cancel/ | Yürüyen işi durdurma. |
| **Skills for Agents** | adk.dev/skills/ | Agent Registry'deki Skill kaynağının ADK karşılığı. |
| **A2A Protocol** | adk.dev/a2a/ | Agent'lar arası protokol, çok agent'lı sistemlerin omurgası. |
| **Callbacks ve Plugins** | adk.dev/callbacks/, adk.dev/plugins/ | Guardrail, politika ve denetim noktalarını kod seviyesinde yerleştirme. |
| **Context compression** | adk.dev/context/compaction/ | Haftalar süren bağlamı bütçe içinde tutma. |
| **Memory** | adk.dev/sessions/memory/ | Memory Bank bağlantısı. |
| **Evaluation** | adk.dev/evaluate/ | Kriterler, kullanıcı simülasyonu, ortam simülasyonu, özel metrikler. |
| **Observability** | adk.dev/observability/ | Logging, metrics, traces. |

### 5.1 Ambient agents: kritik mimari kısıt `[TEYİTLİ]`

Trigger endpoint'leri (`/apps/{app_name}/trigger/pubsub` ve `/trigger/eventarc`) şunları otomatik yapıyor: payload parse, Base64 çözme, event başına oturum oluşturma, semafor ile eşzamanlılık kontrolü (varsayılan 10), üstel geri çekilmeli otomatik retry (varsayılan 3 deneme, 1s taban, 30s tavan).

**Ancak trigger endpoint'leri senkron çalışıyor ve üst servisin zaman aşımına tabi:**

| Servis | Azami süre |
|---|---|
| Pub/Sub push | 10 dakika (ack deadline) |
| Eventarc | 10 dakika |

Doküman açıkça uyarıyor:
> "Trigger endpoints are not suitable for agents that take more than 10 minutes to complete. For long-running workloads, use Pub/Sub pull subscriptions, Cloud Run Jobs, or a worker pool architecture instead."

**Bunun anlamı:** Kategorinin istediği "haftalar süren asenkron operasyon", tek bir uzun trigger çalışması olarak kurulamaz. Doğru mimari, uzun süreci **kısa, idempotent, olay tetiklemeli adımlara bölmek** ve sürekliliği Memory Bank + Sessions üzerinde taşımaktır. Yani "hafızada süreklilik, yürütmede kesiklik".

Bu ayrım mimari kriterinde (%30) tam olarak jürinin aradığı türden bir mühendislik kararı. 13 Ağustos webinar'ının başlığı da bunu işaret ediyor: "Build a Long-Running Agent: crash recovery, human approval, and the idempotency trap, why a resumable agent might order two laptops."

Ayrıca:
- Her yeniden teslim yeni bir oturum yaratıyor, trigger iş yükleri tasarım gereği stateless. Kalıcı `SessionService` (örneğin `DatabaseSessionService`) yapılandırılmazsa oturumlar geçici.
- Dead-letter queue yapılandırılmalı, yoksa tekrar tekrar başarısız olan mesajlar kaybolur.
- Eşzamanlılık kontrolü process başına. Birden fazla Cloud Run instance'ında her biri kendi semaforunu tutar.
- Ambient agent çıktısı bir bildirim kanalına yönlendirilmeli (structured logging + Cloud Monitoring alert, Pub/Sub topic, veya Application Integration).
- Deploy: `adk deploy cloud_run --trigger_sources="pubsub,eventarc"`. Cloud Run şu an ambient agent'lar için önerilen platform.

---

## 6. Model seçimi ve maliyet

### 6.1 Mevcut modeller `[TEYİTLİ]`

| Model | Durum | Not |
|---|---|---|
| `gemini-3.5-flash` | GA, 19 Mayıs 2026 (Google I/O) | Gemini API, AI Studio, Antigravity, GEAP ve Gemini Enterprise'da mevcut. AB çoklu bölge endpoint'i var. |
| `gemini-3.6-flash` | GA, 21 Temmuz 2026 | 3.5 Flash'a göre %17 daha az çıktı token'ı, daha düşük çıktı token maliyeti, daha iyi kod ve çok modlu performans. |
| Gemini 3.5 Flash-Lite | GA, 21 Temmuz 2026 | 3.5 serisinin en hızlısı, saniyede 350 çıktı token'ı. |
| Gemini 3.5 Flash Cyber | Kamu kurumu pilotu | Genel erişime kapalı. |
| Gemini 3.5 Pro | Gecikmiş | Temmuz sonu itibarıyla henüz genel erişimde değil. |

Yarışma "Gemini 3.5 veya daha yenisi" diyor, dolayısıyla üçü de uygun.

`[BELİRSİZ]` Gemini 3.6 Flash'ın duyurusu erişim olarak "Gemini API via AI Studio ve Android Studio" ile "Antigravity" diyor; Vertex AI / Agent Platform açıkça sayılmamış. İkincil bir kaynak Vertex üzerinden erişilebilir olduğunu söylüyor. **Kod yazılmadan önce doğrudan Model Garden'dan doğrulanmalı.** 3.5 Flash'ın GEAP'te olduğu birincil kaynakta teyitli, dolayısıyla güvenli varsayılan odur.

`[BELİRSİZ]` Overview sayfası "leveraging Gemini 3.5 Flash" diye spesifik model adı veriyor; Rules ve FAQ ise "Gemini 3.5 or newer" diyor. Rules bağlayıcı olduğu için daha yeni model kullanmak sorun olmamalı, ama kategori seçiminde emin olmak isteniyorsa sorulabilir.

### 6.2 Kredi ve maliyet `[TEYİTLİ]`

- Google Cloud ücretsiz deneme: https://cloud.google.com/free
- Yarışmaya özel 150 USD kredi, form ile talep ediliyor. Kişi başı bir kod. İnceleme 72 iş saati sürüyor. Verilmesi garanti değil.
- **150 USD'yi aşan tüm ücretlerden katılımcı sorumlu.**
- Kredilerin kapsamadıkları: Marketplace üzerinden faturalanan üçüncü taraf çözümler (MongoDB Atlas, Datadog gibi), Cloud Domains üzerinden alan adı kaydı, bazı yüksek maliyetli GPU/TPU rezervasyonları.
- Agent framework'leri (ADK, GenAI SDK, Antigravity SDK, Genkit) ücretsiz. AI Studio'da Gemini API free tier'da prototipleme ücretsiz.

`[BELİRSİZ]` **Kredi formu için iki farklı link var:**
- Rules sayfası: https://forms.gle/riGhgDSHkHeMx8Ca6
- Resources ve FAQ sayfaları: https://forms.gle/5PtXmw1dSbDnpYke9

Hangisinin geçerli olduğu belli değil. FAQ ve Resources daha güncel görünüyor ve aynı linki veriyor; ancak Rules bağlayıcı belge. Form doldurulmadan önce sorulmalı, ya da doğrudan FAQ'daki link kullanılıp Discussion Board'da teyit alınmalı.

FAQ'nun kredi formu için verdiği tavsiye `[TEYİTLİ]`: form hangi track için inşa edildiğini ve kısa proje tanımını soruyor. **Üç resmî track adından biri yazılmalı, uydurma isim yazılmamalı; çok kısa açıklamalar otomatik reddediliyor.**

### 6.3 Resmî maliyet düşürme tavsiyeleri `[TEYİTLİ]`

- Önce Flash kullan, Pro'yu sadece karmaşık nihai akıl yürütme için sakla
- Minimum instance sayısını 0 tut (scale to zero)
- Küçük RAM/CPU ile başla, azami instance tavanı koy
- Serverless vector search kullan, sürekli açık cluster kurma
- Depolamayı hafif tut, uzun vadeli hafızayı sıkıştır, geçici artefaktları temizle
- Cloud Console'da bütçe uyarısı aç
- Public Cloud Run URL'lerini API key veya kimlik doğrulama ile koru
- Demo çekildikten sonra servisleri kapat ve kullanılmayan kaynakları sil

---

## 7. Kural belirsizlikleri: organizatöre sorulması gerekenler

Bunlar tahmin edilmemeli. Discussion Board (https://allthingsagentichackathon.devpost.com/forum_topics) veya shawni@devpost.com üzerinden sorulmalı.

### 7.1 Jüri alt kriterlerindeki isim uyuşmazlığı `[BELİRSİZ]` EN KRİTİK

Rules sayfasındaki Aşama 2 kriterlerinin alt maddeleri, üç resmî kategori adı yerine **tamamen farklı üç track adı** kullanıyor:

- "The Continuous Action Engine"
- "The Evolving Knowledge Engine"
- "The Multi-Agent Nexus"

Bu isimler yarışmanın hiçbir yerinde tanımlı değil. Üç resmî kategori Taskmaster, Collaborative Partner ve Fortified Enterprise Fleet.

`[ÇIKARIM]` İçerik olarak eşleşme muhtemelen şöyle:
- Continuous Action Engine ≈ Taskmaster ("multi-step background workflow", "Bring Your Own Friction" mandası)
- Evolving Knowledge Engine ≈ Collaborative Partner ("synthesize or mutate data", "messy unstructured data streams")
- **Multi-Agent Nexus ≈ Fortified Enterprise Fleet** ("multi-agent system", "specialized sub-agents'a akıllı delegasyon", "Unlikely Hero")

Eğer bu eşleşme doğruysa, Fleet kategorisinde jürinin alt kriterleri şunlar olur:

**Innovation & Operational Utility (%40) için:**
- Görev, çok agent'lı bir sistemi gerektirecek kadar karmaşık mı?
- Sistem, uzmanlaşmış alt agent'lara akıllıca delege ediyor mu?
- Bunu standart kurumsal rollerin dışındaki bir **"Unlikely Hero"** için mi inşa ettiler?

**Architectural Discipline (%30) için:**
- Agent'lar arasında net, katı biçimde uygulanan sorumluluk ayrımı var mı?
- Agent'lar arası yönlendirme mantığı hata toleranslı mı? Bir worker agent döngüye girerse veya halüsinasyon döndürürse sistem nasıl toparlanıyor?

Bu alt kriterler doğrulanabilirse **"Unlikely Hero"** maddesi fikir seçiminin merkezine yerleşir: standart kurumsal rol (satın alma müdürü, İK, finans) dışında bir kullanıcı seçmek doğrudan puan getirir. Google'ın kendi örneği bir satın alma müdürü olduğu için bu, klon riskinden kaçmanın da yolu.

**Sorulacak soru:** "The Rules page lists sub-criteria under three track names (Continuous Action Engine, Evolving Knowledge Engine, Multi-Agent Nexus) that do not match the three official categories. Which sub-criteria apply to a Fortified Enterprise Fleet submission?"

### 7.2 GEAP kullanımının bonus puan durumu `[BELİRSİZ]`

FAQ, Fleet track hakkında şöyle diyor: "deploying on the Agent Platform earns bonus points."

Ancak Rules sayfasındaki Aşama 3 bonus listesinde sadece üç kalem var: içerik yayını, sosyal medya, ek Google AI modeli. GEAP deployment'ı bonus olarak listelenmemiş.

**Sorulacak soru:** "The FAQ says deploying on the Gemini Enterprise Agent Platform earns bonus points for the Fortified Enterprise Fleet track, but the Official Rules Stage Three bonus list does not include it. Is GEAP deployment a scored bonus, and if so how many points?"

### 7.3 Diğer sorular

- Kredi formu: hangi link geçerli? (bkz. 6.2)
- Best Architectural Design ve Individual/Hobbyist ödülleri, kategori ödülüyle aynı anda hedeflenebilir mi, yoksa "bir proje bir ödül" kuralı gereği otomatik olarak sadece en yükseği mi verilir?
- Kategori beyanı teslimden sonra değiştirilebilir mi? (Rules, Sponsor'a yeniden atama hakkı veriyor ama katılımcının değiştirme hakkından söz etmiyor.)

---

## 8. Fizibilite kapıları: kod yazılmadan ölçülmesi gerekenler

Fikir seçimine geçmeden önce bunlar test edilmeli. Ölçüm sonucu olumsuzsa fikir elenir, bu kayıp değil kazançtır.

| # | Ölçüm | Neden | Olumsuzsa sonuç |
|---|---|---|---|
| 1 | GEAP bileşenlerinin hesapta gerçekten açılabildiği (Agent Registry, Agent Runtime, Memory Bank, Agent Gateway, Model Armor API'leri) | Bazıları preview veya sınırlı bölge olabilir. Türkiye'den erişim ve bölge seçimi doğrulanmalı. | Erişilemeyen bileşen mimariden çıkar, kategori beyanı zayıflar |
| 2 | 150 USD kredinin gelip gelmediği | 72 iş saati inceleme var, verilmesi garanti değil | Kapsam ücretsiz katmana sığacak şekilde daraltılır |
| 3 | Gemini 3.6 Flash'ın Agent Platform üzerinden erişilebilirliği | Maliyet avantajı %17 daha az çıktı token'ı | 3.5 Flash'a düşülür, bütçe yeniden hesaplanır |
| 4 | Model Armor'ın Türkçe prompt injection tespit oranı | Türkçe test edilmemiş dil listesinde | Ölçüm yapılırsa güçlü bir katkı; yapılmazsa Türkçe guardrail iddiası kurulamaz |
| 5 | Kullanılacak "production data" kaynağı | Kategori "production data" ile etkileşim istiyor. Gerçek hasta/müvekkil verisi kullanılamaz. | Sentetik ama gerçekçi bir kurumsal veri kümesi üretilir ve **açıkça sentetik olduğu etiketlenir** |
| 6 | Agent Registry'nin kaç agent'ı gerçekten katalogladığı ve keşif akışının çalıştığı | "cataloged for cross-department use" kanıtlanamazsa kategori beyanı boşa düşer | Kategori değişikliği veya kapsam daraltması |

**Madde 5 üzerine özel not:** Özge'nin elindeki en zengin gerçek veri (hukuki dosyalar, klinik varyant verisi) bu yarışmada kullanılamaz. Hassas veri kuralları sıkıştırılamaz disiplin listesinde. Sentetik veri kullanılacaksa videoda ve README'de "synthetic data" olarak etiketlenmeli. Bu bir zayıflık değil, doğru biçimde sunulursa kurumsal olgunluk göstergesi.

---

## 9. Sıkıştırılamaz disiplin listesi

Zaman daralınca ilk feda edilmek istenenler genelde buradan gelir. Bunlar feda edilmez:

- Uydurma yasağı: sahte çıktı, sahte metrik, sahte atıf, cherry-picked demo yok
- Mock veya kayıtlı olan her şey dürüstçe etiketlenir (Rules zaten "Fake or overstate what's running" uyarısını FAQ'da yapıyor)
- İddia edilen her sayının arkasında görülebilir artefakt olur
- Secret taraması, gizli anahtar repoya girmez (Model Armor'ın SDP filtresi GCP credential ve API key tespit ediyor, kendi repoda da kullanılabilir)
- Lisans uyumu: kendi lisansın ve tüm bağımlılıklar
- Hassas veri kuralları, anonimleştirme, izin
- Tek komut kurulumun gerçekten çalışması (README spin-up talimatı ayrı bir submission alanı)

---

## 10. Doğrudan doküman haritası

Bir agent'a verilecek çalışma referansları.

### Yarışma
- Ana sayfa: https://allthingsagentichackathon.devpost.com/
- Kurallar (bağlayıcı): https://allthingsagentichackathon.devpost.com/rules
- Kaynaklar (track derinlemesine): https://allthingsagentichackathon.devpost.com/resources
- SSS: https://allthingsagentichackathon.devpost.com/details/faqs
- Güncellemeler: https://allthingsagentichackathon.devpost.com/updates
- Tartışma panosu: https://allthingsagentichackathon.devpost.com/forum_topics
- Devpost Discord: https://discord.gg/HP4BhW3hnp

### Webinar'lar (Google, ücretsiz, kayıtlı izlenebilir)
- 11 Ağu: Architecting Multi-Agent Teams, ADK 2'nin üç orkestrasyon deseni
  https://cloudonair.withgoogle.com/events/architecting-multi-agent-teams-mastering-three-orchestration-patterns-adk-2
- 13 Ağu: Build a Long-Running Agent, kalıcı iş akışları, crash recovery, idempotency tuzağı
  https://cloudonair.withgoogle.com/events/build-long-running-agent-persistent-workflows-google-adk
- 20 Ağu: Build a Self-Evolving Agent
  https://cloudonair.withgoogle.com/events/build-self-evolving-agent-autonomous-self-improvement
- 27 Ağu: Architecting Agent Memory, session state, vector search, managed cloud memory
  https://cloudonair.withgoogle.com/events/architecting-agent-memory-session-state-vector-search-managed-cloud-memory

11 ve 13 Ağustos oturumları Fleet kategorisinin tam merkezinde.

### GEAP
- Doküman ana sayfa: https://docs.cloud.google.com/gemini-enterprise-agent-platform
- Platform genel bakış: https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview
- Duyuru blogu: https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform
- Agent Runtime: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime
- ADK ile Agent Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk
- Agent deploy: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent
- Runtime contract (özel container): https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/runtime-contract
- Memory Bank: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
- Memory Bank ADK quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart
- Memory Bank IAM conditions: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/iam-conditions
- Sessions: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions
- Agent Registry (GEAP içi): https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry
- Agent Registry (kendi dokümanı): https://docs.cloud.google.com/agent-registry/overview
- Agent Registry data model: https://docs.cloud.google.com/agent-registry/data-model
- Agent Registry setup: https://docs.cloud.google.com/agent-registry/setup
- Agent kaydetme: https://docs.cloud.google.com/agent-registry/register-agents
- ADK ile orkestratör kurma: https://docs.cloud.google.com/agent-registry/resolve-endpoints-and-build-orchestrators
- Agent Identity: https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview
- Agent Identity + Runtime: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity
- Agent Gateway: https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview
- Gateway kurulumu: https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway
- Model Armor genel bakış: https://docs.cloud.google.com/model-armor/overview
- Model Armor'ı gateway'e bağlama: https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor
- Model Armor + Agent Platform: https://docs.cloud.google.com/model-armor/model-armor-vertex-integration
- Model Armor veri yerleşikliği: https://docs.cloud.google.com/model-armor/data-residency
- Observability: https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/observability/overview
- Agent trace görüntüleme: https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/observability/traces
- Semantic governance policies: https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview
- Güvenlik bulguları: https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/view-security-findings

### Codelab'ler (uygulamalı, Fleet kategorisi için en hızlı yol)
- Agent Platform ile agentic iş yüklerini yönetme: https://codelabs.developers.google.com/cloudnet-agent-gateway
- Agent Runtime'dan Google MCP server'lara egress: https://codelabs.developers.google.com/agw-cuj-arun-egress-gmcp
- Harici MCP server'lara egress: https://codelabs.developers.google.com/agw-cuj-arun-egress-emcp
- VPC ağına egress: https://codelabs.developers.google.com/agw-cuj-arun-egress-vpc

### ADK
- Ana sayfa: https://adk.dev
- Python başlangıç: https://adk.dev/get-started/python/
- Google Cloud kurulumu: https://adk.dev/get-started/google-cloud/
- Graph Workflows: https://adk.dev/graphs/
- Multi-Agent Workflows: https://adk.dev/workflows/
- Workflow desenleri: https://adk.dev/workflows/patterns/
- Ambient Agents: https://adk.dev/runtime/ambient-agents/
- Resume Agents: https://adk.dev/runtime/resume/
- Cancel Agent Runs: https://adk.dev/runtime/cancel/
- Sessions: https://adk.dev/sessions/session/
- Memory: https://adk.dev/sessions/memory/
- Context compression: https://adk.dev/context/compaction/
- Callbacks: https://adk.dev/callbacks/types-of-callbacks/
- Plugins: https://adk.dev/plugins/
- Skills: https://adk.dev/skills/
- MCP tools: https://adk.dev/tools-custom/mcp-tools/
- A2A protokolü: https://adk.dev/a2a/intro/
- Safety and Security: https://adk.dev/safety/
- Observability: https://adk.dev/observability/
- Evaluation: https://adk.dev/evaluate/
- Cloud Run'a deploy: https://adk.dev/deploy/cloud-run/
- Agent Runtime'a deploy: https://adk.dev/deploy/agent-runtime/
- Agents CLI: https://adk.dev/deploy/agent-runtime/agents-cli/ ve https://google.github.io/agents-cli/
- ADK 2.0 notları: https://adk.dev/2.0/
- Python repo: https://github.com/google/adk-python

### Model ve öğrenme
- Gemini API: https://ai.google.dev
- Google AI Studio: https://aistudio.google.com
- Genkit: https://firebase.google.com/docs/genkit
- Antigravity SDK: https://antigravity.google/docs/sdk
- GEAR programı (ücretsiz): https://developers.google.com/program/gear
- Introduction to Agents yolu: https://www.skills.google/paths/3546
- GEAR SSS: https://developers.google.com/profile/help/gear

Not: GEAR (Gemini Enterprise Agent Ready) bir **öğrenme programı**, GEAP (Gemini Enterprise Agent Platform) bir **ürün ailesi**. İsimler benziyor, karıştırılmamalı.

---

## 11. Bu raporun kapsamadıkları

Aşağıdakiler bilinçli olarak bu belgede yok, sonraki fazların konusu:

- Fikir adayları ve eleme (Faz 1). En az üç aday, klon riski, adıyla kullanıcı, haksız avantaj, şaşırtan kullanım, IP koruması ve demo edilebilirlik testlerinden geçirilecek.
- Kapsam kilidi, kesme listesi, freeze tarihi (Faz 2). Zaman bütçesi Özge'nin kararı.
- Teknik mimari kararları (Faz 3).
- Demo senaryosu ve teslim paketi (Faz 4 ve 5).

Ayrıca **proje galerisi henüz yayınlanmamış**, dolayısıyla rakip taraması yapılamadı. Galeri açıldığında Fortified Enterprise Fleet filtresiyle kaç projenin geldiği ve ne yaptıkları kontrol edilmeli. Bu, klon riski değerlendirmesinin gerçek verisi olacak.
