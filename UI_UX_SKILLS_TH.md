# สกิล UI/UX ที่ติดตั้งตามบทความ

ที่มา: [มัดรวม Agent Skills สำหรับงาน UX/UI ที่ควรมีติดเครื่อง](https://xiengperm.dev/posts/agent-skills-for-ui-ux-th/)

ติดตั้งวันที่ **23 ตุลาคม 2026** สำหรับ Codex ในโปรเจกต์นี้ที่ `.agents/skills/` รวม **21 สกิล**: เพิ่มใหม่ 20 และใช้ Taste Skill ที่ติดตั้งสำเร็จแล้ว 1 ตัว ไม่เปลี่ยนหน้าเว็บ dependencies ของแอป หรือบริการ Airflow

## รายการที่ติดตั้ง

| ต้นทาง | สกิลในเครื่อง |
| --- | --- |
| anthropics/skills | `frontend-design`, `brand-guidelines`, `webapp-testing` |
| nextlevelbuilder/ui-ux-pro-max-skill | `ui-ux-pro-max` |
| Leonxlnx/taste-skill | `design-taste-frontend` |
| pbakaus/impeccable | `impeccable` พร้อมชุดคำสั่งใน reference |
| nutlope/hallmark | `hallmark` |
| arvindrk/extract-design-system | `extract-design-system` |
| emilkowalski/skills | `emil-design-eng`, `review-animations`, `animation-vocabulary` |
| vercel-labs/agent-skills | `web-design-guidelines`, `vercel-react-best-practices`, `vercel-composition-patterns` |
| AccessLint/skills | `accessibility-scan`, `accessibility-audit`, `accessibility-diff`, `accessibility-inspect`, `accessibility-fix` |
| shadcn-ui/ui | `shadcn` |
| sleekdotdesign/agent-skills | `sleek-design-mobile-apps` |

AccessLint เพิ่ม inspect/fix เพื่อให้ชุด audit มีสกิลประกอบครบ พร้อม `shared/methodology.md` ซึ่งไม่ใช่สกิลแยก ต้นทางบางชุดเปลี่ยนจากวันที่เขียนบทความ เช่น Taste ปัจจุบันมีสกิลหลักหนึ่งตัว และ Impeccable รวมคำสั่งไว้ในสกิลหลัก

## ใช้อย่างไร

สกิลพร้อมให้ agent โหลดในเทิร์นถัดไป สามารถระบุชื่อให้ชัด เช่น:

- `ใช้ ui-ux-pro-max ช่วยวาง dashboard ให้ตรงข้อมูลจริง`
- `ใช้ web-design-guidelines ตรวจหน้าเว็บนี้`
- `ใช้ accessibility-scan ตรวจ http://localhost:8091`
- `ใช้ design-taste-frontend ออกแบบหน้าแสดงผลตามโจทย์นี้`

ใช้เฉพาะตัวที่เหมาะกับงาน ไม่สั่งทำทุก workflow พร้อมกัน โดยยังรักษา Ponytail และขอบเขตเตรียมสอบ: ไม่เปลี่ยน stack หรือสร้างฟีเจอร์ที่โจทย์ไม่ได้ขอ React/shadcn ใช้เมื่อมีโปรเจกต์ที่ใช้เครื่องมือนั้นจริง ส่วน brand-guidelines เป็นแบรนด์ Anthropic ไม่ใช่คำสั่งให้เปลี่ยนแบรนด์โปรเจกต์นี้

`DESIGN.md` ปัจจุบันเป็นเอกสารสถาปัตยกรรม Pipeline อย่าเขียนทับด้วย design tokens โดยพลการ ให้แยกเอกสาร UI เมื่อจำเป็น

## การปรับให้ใช้ในเครื่องนี้

- UI UX Pro Max: ปรับ path ตัวอย่างจาก `${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max` เป็น `.agents/skills/ui-ux-pro-max` สำหรับ Codex และเก็บ scripts/data/references ครบ
- AccessLint: เก็บ shared methodology ที่สกิลอ้างถึงไว้เป็น sibling directory
- ล็อก source revision และ hash ใน `ui-ux-skills-lock.json`; Taste ใช้ provenance ที่มีอยู่ใน `skills-lock.json`
- ไม่แตะสกิลระดับผู้ใช้ที่ชื่อซ้ำกันใน `C:/Users/pasit/.agents/skills` ตัวที่ติดตั้งในโปรเจกต์เป็นอีกชุด
- กัน `.agents/` และ `.codex/` จาก Docker build context และกราฟโค้ด

## สิ่งที่ยังไม่ได้เชื่อมจากบทความ

| รายการ | สถานะ |
| --- | --- |
| getdesign.md | เป็นเว็บแคตตาล็อก ไม่ใช่สกิลที่มีตัวติดตั้ง ไม่คัดลอก DESIGN.md ของแบรนด์มาใส่อัตโนมัติ |
| Magic MCP / 21st.dev | ยังไม่เชื่อม MCP หรือขอ API key |
| Figma MCP | ยังไม่เชื่อมบัญชี Figma |
| Superdesign | ยังไม่เปิดบัญชีหรือ export สกิลจากแอป บทความไม่มีคำสั่งติดตั้งแบบตายตัว |
| Sleek | ติดตั้งไฟล์สกิลแล้ว แต่ยังไม่ตั้งบัญชี/API key ของบริการ |

การติดตั้งสกิลไม่เท่ากับเปิด runtime ทุกตัว: Playwright/browser, AccessLint MCP, Impeccable binary หรือแพ็กเกจ npm ของตัวดึง design tokens อาจต้องเตรียมเพิ่มเติมเมื่อเรียกใช้จริง รอบนี้ไม่เปิดบริการภายนอก ไม่ใช้บัญชีแบบเสียเงิน และไม่เปลี่ยนหน้าเว็บ

## สิ่งที่ตรวจแล้ว

- พบ `SKILL.md` ครบ 21 ชื่อไม่ซ้ำ และชื่อใน frontmatter ตรงกับ directory
- shared reference ของ AccessLint และ launcher หลักของ UI UX Pro Max, Impeccable, Hallmark อยู่ครบ
- UI UX Pro Max เรียกตัวค้นหา local ได้
- `webapp-testing/scripts/with_server.py --help` ทำงาน
- `node --check` ของ Hallmark sloplint ผ่าน

ยังไม่ได้ทดลอง workflow ออกแบบ/ตรวจเว็บครบทั้ง 21 ตัว และไม่ได้ audit ความปลอดภัยของ upstream ทุกไฟล์
