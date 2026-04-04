<h1 align="center">Study Buddy!</h1>

![TypeScript](https://img.shields.io/badge/TypeScript-%2398b3d2?style=flat&logo=TypeScript&logoColor=%231f37b8)
![Python](https://img.shields.io/badge/Python-%23ce8484?style=flat&logo=Python)
![CSS](https://img.shields.io/badge/CSS-purple?style=flat&logo=CSS)
![Node](https://img.shields.io/badge/Node.js-%23e0dacb?style=flat&logo=Node.js)
![React](https://img.shields.io/badge/React-%23cecccc?style=flat&logo=React)
![Docker](https://img.shields.io/badge/Docker-%23e2faff?style=flat&logo=Docker)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

Study Buddy allows users to generate concise notes from PDF, DOCX, and PPTX files using artificial intelligence. 

Try the app here:
[study-buddy-notes.vercel.app](https://study-buddy-notes.vercel.app/)

## Usage and Demo
1. On the welcome page, click on the "Select Files" button to begin.
![File Upload Page](src/demo-images/file_upload_page.png)

2. Select relevant files in PDF, DOCX, or PPTX, up to 10 MB total.
![File Select](src/demo-images/file_select.png)

3. Once all desired files are selected, click on the "Generate AI Notes" button.
![Files Uploaded](src/demo-images/uploaded.png)

4. Wait for file processing and note generation to complete.
![File Processing](src/demo-images/processing.png)

5. Notes are generated! View the notes using the in-app PDF viewer. Click the "Copy to Clipboard" button to copy the note's as raw LaTeX. Once finished, click the "Process New Documents" button to return to the initial file upload page.
![Notes Generated](src/demo-images/notes_generated.png)

6. Alternatively, click the "Open PDF" button to open the PDF in a new tab, from where the notes can be downloaded.
![PDF Viewer](src/demo-images/pdf_view.png)

## Tech Stack
Frontend: 
- React
- TypeScript

Backend: 
- Node.js / Express
- Python

Infrastructure: 
- Docker
