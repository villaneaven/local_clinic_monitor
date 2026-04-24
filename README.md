
# Local Clinic Check-In Monitor

This is a standalone Python app. It does **not** connect to SharePoint.

It gives you:
- Room list
- Patient check-in
- Check-out / clear room
- Live wait time
- Color-coded wait alerts
- Local saved data in `clinic_queue.json`

## Install

Open Command Prompt or PowerShell in this folder and run:

```bash
pip install -r requirements.txt
```

## Start the app

```bash
streamlit run app.py
```

The app will open in your browser.

## Use it on a clinic monitor

1. Start the app.
2. Open the Streamlit browser page.
3. Put the browser in full-screen mode.
4. Leave it running on the clinic TV or monitor.

## Data storage

The app saves data in this local file:

```text
clinic_queue.json
```

Do not delete that file unless you want to reset the room list and queue.

## Customize rooms

You can add or remove rooms from the sidebar inside the app.
