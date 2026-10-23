# หัวข้อที่ตรวจว่าดึงข้อมูลได้จริง

วันที่ตรวจ: 23 ตุลาคม 2026 ผู้ใช้ต้องการหัวข้อที่ทำไม่ยากและดึงข้อมูลได้ ยังไม่ถือว่าเลือกหัวข้อจริง ไม่เปลี่ยน contract หรือเปิดระบบ Docker ในรอบสำรวจนี้

## ตัวเลือกใหม่: ข้อมูล Pokémon หมายเลข 1–151 จาก 3 แหล่ง

ผู้ใช้แจ้งว่ามีเพื่อนเลือกหัวข้อ Bitcoin แล้ว จึงตัดหัวข้อนั้นออกจากตัวเลือกสำหรับงานนี้ ข้อกำหนดล่าสุดมี scraping อย่างน้อยหนึ่งแหล่ง ห้าม Selenium และต้องเหลือข้อมูลอย่างน้อย 100 รายการหลังรวม

เสนอหมวดข้อมูลเกม ขอบเขต Pokémon หมายเลข National Pokédex 1–151 เฉพาะร่างปกติ รวมชื่อ ประเภทและ base stats จาก:

1. Pokémon Database: https://pokemondb.net/pokedex/all — HTTP 200, มีตาราง HTML 1,262 แถวรวม header/หลายร่าง; ต้องกรองหมายเลขและร่างปกติ เป็นแหล่ง web scraping โดยไม่ใช้ Selenium
2. PokéAPI: https://pokeapi.co/api/v2/pokemon?limit=151&offset=0 — HTTP 200, รายชื่อ 151 รายการ; ต้องอ่าน detail URL เพื่อได้ stats/types ทดลอง detail หมายเลข 1 แล้วได้หก stats
3. Pokémon Showdown: https://play.pokemonshowdown.com/data/pokedex.json — HTTP 200, กรอง num 1–151 และไม่เอา forme ได้ 151 รายการ มี types/baseStats

ตรวจ robots.txt ของทั้งสามโดเมนแล้ว parser อนุญาต endpoint สำหรับ User-Agent ของโครงงาน โดย Pokémon Database กำหนด crawl-delay 2 วินาที ต้องใช้ agent ของโปรแกรมจริงและตรวจ rules อีกครั้งเมื่อรัน ตัวดึง PokéAPI ต้อง cache/จำกัดความถี่ตาม Fair Use Policy

ใช้หมายเลข Pokédex เป็นคีย์รวมและ UPSERT หลังกรองร่าง ไม่ใช้ชื่ออย่างเดียว เพราะชื่อแต่ละแหล่งต่างรูปแบบได้ เป้าหมายหลัง dedup คือ 151 ตัว ไม่เอา Mega/Regional forms มารวมผิดตัว dashboard อาจแสดง KPI จำนวนตัว/ค่าสถิติเฉลี่ย กราฟประเภท ตัวกรอง และตารางเปรียบเทียบ พร้อม provenance และสถานะ pipeline

ยังเป็นข้อเสนอ ไม่ได้เลือกแทนผู้ใช้ ไม่ได้เขียน parser เต็มหรือโหลดข้อมูลเข้าฐาน ต้องทดสอบว่าได้ครบ 151 หลังรวมจริงก่อนยืนยันผ่านเกณฑ์

## ตัวเลือกเดิมที่ตัดออกแล้ว: เปรียบเทียบราคา Bitcoin จาก 3 กระดานซื้อขาย

หมวด: ราคาสินทรัพย์ดิจิทัล

ขอบเขตเริ่มต้น: ราคา last trade ของ Bitcoin คู่ USD จาก Coinbase Exchange, Kraken และ Bitstamp เก็บ snapshot ตามรอบ Airflow รวมเป็นตารางเดียวใน PostgreSQL และแสดงราคา/ส่วนต่าง/แนวโน้มบนเว็บที่พัฒนาเอง ใช้หัวข้อนี้เมื่ออาจารย์อนุญาตให้เลือกนอกหมวดตัวอย่างได้

| แหล่ง | Public API ที่ทดสอบ | ผล |
| --- | --- | --- |
| Coinbase Exchange | https://api.exchange.coinbase.com/products/BTC-USD/ticker | HTTP 200, อ่าน JSON และ price ได้ |
| Kraken | https://api.kraken.com/0/public/Ticker?pair=XBTUSD | HTTP 200, ไม่มี API error, อ่าน c[0] ได้ |
| Bitstamp | https://www.bitstamp.net/api/v2/ticker/btcusd/ | HTTP 200, อ่าน JSON และ last ได้ |

ทดสอบจากเครื่องนี้โดยไม่ใช้ API key หรือบัญชีซื้อขาย และไม่มีการทำธุรกรรม ผลตรวจไม่รับประกันว่า API จะเปิดตลอดเวลา ต้องจัดการ timeout/retry/rate limit ใน implementation

เหตุผลที่ประเมินว่าทำง่าย: ข้อมูลเป็น JSON ไม่ต้องใช้ browser automation, ใช้คู่เงิน USD เหมือนกัน และทั้งสามแหล่งเป็นคนละตลาดจริง ต้อง normalize XBT ของ Kraken เป็น BTC ไม่ผสม USD กับ USDT

ตารางรวมขั้นต่ำ: source, symbol, quote_currency, last_price, collected_at, source_url ราคาต้องเป็น numeric และเวลาต้องมี timezone คีย์ snapshot ใช้ source/symbol/รอบที่เก็บ การ retry รอบเดิมต้องไม่เพิ่มแถวซ้ำ

DAG ที่เสนอ: extract_coinbase / extract_kraken / extract_bitstamp → normalize_merge_validate → load_postgres → summarize งานนี้ยังไม่ถูกสร้าง

Dashboard ที่เสนอ: ราคาแยกแหล่ง ส่วนต่างสูงสุด–ต่ำสุดต่อรอบ กราฟแนวโน้ม และตารางข้อมูลพร้อมเวลาเก็บ ไม่แสดงการจัดอันดับกำไรหรือคำแนะนำซื้อขาย

ข้อจำกัด: snapshot เกิดคนละเวลาและแต่ละตลาดอาจมี last trade คนละเวลา แสดงเวลาเก็บให้ชัดและไม่เรียกว่าเป็นราคาพร้อมกันแบบ real-time ประวัติของระบบเริ่มเมื่อเริ่มเก็บจริง ถ้าต้องการประวัติย้อนหลังต้องเพิ่มขั้นดึง historical data ที่เทียบช่วงเวลาได้

เอกสาร API: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductticker , https://docs.kraken.com/api/docs/rest-api/get-ticker-information/ , https://www.bitstamp.net/api/

## ตัวเลือกที่ตรงตัวอย่างอาจารย์: ประกาศงาน Data Engineer ในกรุงเทพฯ

ทดสอบอ่านหน้าสาธารณะจาก 3 เว็บได้ HTTP 200:

- JobThai: https://www.jobthai.com/th/job/1933547 — มี Next.js data
- JOBBKK: https://www.jobbkk.com/jobs/detailurgent/207342/1225430 — มี structured data
- JobTopGun: https://www.jobtopgun.com/th/jobs/j17590-52 — มี structured data

ประเมินว่ายากกว่า API ราคาคริปโต เพราะต้องทำ discovery/pagination, parser แยกตามเว็บ, ตรวจประกาศซ้ำข้ามเว็บ และจัดการเงินเดือน/สถานที่ไม่ครบ การอ่านหน้าได้ยังไม่ยืนยันสิทธิ์การนำข้อมูลไปใช้หรือความสำเร็จของ parser เต็มระบบ ต้องตรวจเงื่อนไขของแต่ละเว็บก่อนทำตัวดึงจริง

หากใช้ขอบเขตกรุงเทพฯ ต้องไม่รวมประกาศที่บอกเพียงกรุงเทพและปริมณฑลว่าเป็นกรุงเทพฯ โดยไม่มีข้อมูลยืนยัน เลือกขยายขอบเขตหรือแยกสถานที่ไม่ชัดเจนอย่างตรงไปตรงมา
