# สกิลในเครื่องสำหรับโปรเจกต์นี้

ตรวจไฟล์ `SKILL.md` ในเครื่องวันที่ **23 ตุลาคม 2026** รอบแรกค้นเฉพาะในเครื่อง ต่อมาติดตั้ง Graphify และสกิล UI/UX เพิ่มตามคำขอผู้ใช้ รายการนี้ยืนยันการมีไฟล์และความเกี่ยวข้อง ไม่ได้ตรวจรับรองคุณภาพของ community skill ทั้งหมด

สกิล UI/UX ตามบทความติดตั้งระดับโปรเจกต์แล้ว 21 ตัว ดู [รายชื่อ วิธีใช้ และข้อจำกัด](UI_UX_SKILLS_TH.md) และ source revision ใน `ui-ux-skills-lock.json`

## ใช้ในรอบสร้างโครง

| สกิล | ใช้ทำอะไร | ที่อยู่จริง |
| --- | --- | --- |
| ponytail:ponytail | ทำส่วนที่จำเป็นให้ครบ หลีกเลี่ยงฟีเจอร์ที่ยังไม่มีข้อมูลรองรับ | [SKILL.md](C:/Users/pasit/.codex/plugins/cache/ponytail/ponytail/5.3.2/skills/ponytail/SKILL.md) |
| find-skills | แนวทางค้นสกิล โดยจำกัดเฉพาะในเครื่องตามคำขอ | [SKILL.md](C:/Users/pasit/.agents/skills/find-skills/SKILL.md) |
| data-engineer | วาง contract, ingestion, validation และ audit | [SKILL.md](C:/Users/pasit/.agents/skills/data-engineer/SKILL.md) |
| airflow-dag-patterns | DAG แบบ manual, retry, idempotency และ observability | [SKILL.md](C:/Users/pasit/.agents/skills/airflow-dag-patterns/SKILL.md) |
| docker-expert | Build และเปิดชุดบริการ Airflow/PostgreSQL/เว็บ พร้อมตรวจ runtime | [SKILL.md](C:/Users/pasit/.agents/skills/docker-expert/SKILL.md) |
| graphify | ติดตั้งเพิ่มตามคำขอผู้ใช้เพื่อค้นความสัมพันธ์และนำทางโค้ดผ่านกราฟ local | [SKILL.md](.codex/skills/graphify/SKILL.md) |

## พบในเครื่อง เหมาะกับขั้นถัดไป

| สกิล | จังหวะที่ควรใช้ | ที่อยู่จริง |
| --- | --- | --- |
| data-quality-frameworks | เพิ่มกฎชนิดข้อมูล ช่วงค่า และ null policy เมื่อมีข้อมูลจริง | [SKILL.md](C:/Users/pasit/.agents/skills/data-quality-frameworks/SKILL.md) |
| database-design | ออกแบบ grain, fact/dimension และ index ตามคำถามจริง | [SKILL.md](C:/Users/pasit/.agents/skills/database-design/SKILL.md) |
| python-testing-patterns | เพิ่มการทดสอบกฎเฉพาะชุดข้อมูล | [SKILL.md](C:/Users/pasit/.agents/skills/python-testing-patterns/SKILL.md) |
| frontend-design | ขยายหน้าเว็บเป็น dashboard เมื่อทราบตัวชี้วัด | [SKILL.md](C:/Users/pasit/.agents/skills/frontend-design/SKILL.md) |
| doc-coauthoring | เขียนข้อเสนอ รายงาน และข้อจำกัดโดยใช้หลักฐานจริง | [SKILL.md](C:/Users/pasit/.agents/skills/doc-coauthoring/SKILL.md) |

ไม่คัดลอกทุกสกิลเข้ามาใน repo และไม่กำหนดให้เรียกทั้งหมดทุกครั้ง ที่อยู่เหล่านี้เป็น path ของเครื่องนี้ เมื่อย้ายเครื่องให้ค้นหาสกิลใหม่
