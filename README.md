# Talya

Talya Healthcare Management Platform

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd /path/to/bench
bench get-app https://github.com/nagigithup/talya.git --branch version-16
bench --site YOUR_SITE install-app talya
```

Requires Python 3.14 and Frappe, ERPNext and Healthcare 16. Embedded messaging
additionally requires the separate official WhatsApp app; it is optional for the
website and manual contact workflow. Reminders are disabled by default.

- [Reception workflow and configuration](docs/patient-inquiries.md)
- [Release verification and cloud update steps](docs/talya-release.md)
- [P0 recipient-safety remediation](docs/talya-p0-remediation.md)

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/talya
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

## License

mit
