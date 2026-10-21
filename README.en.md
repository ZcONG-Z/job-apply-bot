# job-apply-bot

**Stop retyping your resume into job application forms.**

[中文](README.md) · [Design](docs/design.md) · [Adapter spec](docs/adapter-spec.md) · [Roadmap](docs/roadmap.md)

> **⚠️ Early stage:** this repository currently contains the skeleton and specs only — no runnable code yet. See [docs/roadmap.md](docs/roadmap.md).

## What it does

One structured resume (`profile.json`) drives form filling across multiple Chinese job application systems (Moka, Beisen, NowCoder).

You drop in a resume, the tool parses it into structured data and asks you to confirm, then fills the real form in a real browser — name, contact info, education, internships, attachments — and **stops right before the submit button**.

## What it deliberately does not do

- **No CAPTCHA bypass.** It pauses and hands control back to you.
- **No auto-submit.** Ever.
- **No anti-detection tricks.** No fingerprint spoofing, no fake mouse trails, no `navigator.webdriver` patching.
- **No mass applying.** Single account, serial, rate-limited.

If you want a tool that blasts hundreds of applications, this isn't it.

## Design highlights

- **Declarative adapters.** A site adapter is a YAML file, not a script. Adding a site requires no Python.
- **`profile.json` as the single source of truth.** Store facts, not formats; adapters convert on read.
- **Read-back verification.** Every filled field is read back and diffed against the expected value, producing a per-field report plus screenshots.
- **Label-text-first locators.** Visible label text → aria/placeholder → `name` attribute → CSS path. DOM structure changes; the word "姓名" doesn't.

## Data safety

`profile.json`, `.auth/`, `resumes/`, `inbox/`, `runs/` and `*.db` are all gitignored. Logs mask ID numbers and phone numbers. CI fails if personal data files are staged.

Read [SECURITY.md](SECURITY.md) before contributing — especially the section on what to do if you accidentally commit your resume.

## Contributing

Most valuable contributions are **not** code:

1. **Field intel** — what odd fields did a system ask you for?
2. **Adapters** — one YAML file per site
3. **Anonymized resume samples** — the weirder the layout, the better

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Zhou Cong
