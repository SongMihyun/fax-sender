# FaxSender

GitHub Pages에 올릴 수 있는 브라우저 전용 PDF 동의서 처리 웹앱입니다.

## 목적

FaxSender는 사용자가 브라우저에서 PDF를 업로드하면 서버, DB, 로컬 저장 없이 브라우저 메모리 안에서 체크와 서명을 합성하고 결과 PDF 미리보기와 다운로드를 제공합니다.

## 개인정보 처리

업로드한 PDF와 입력한 고객명, 팀장명, 팀장코드는 서버로 전송되지 않습니다. 모든 처리는 `File`, `ArrayBuffer`, `Blob URL`을 사용해 브라우저 내부에서 수행됩니다.

## 주요 기능

- PDF 파일 선택 및 드래그앤드롭
- 기본 템플릿 좌표 JSON 제공
- 고객명, 팀장명, 팀장코드, 날짜 입력
- 체크 자동 삽입
- 고객명 기반 서명 이미지 생성
- 랜덤 rotation, opacity, scale 적용
- pdf-lib 기반 PDF 합성
- pdf.js 기반 원본/결과 PDF 미리보기
- `{팀장코드}_{팀장명}_{고객명}.pdf` 파일명으로 다운로드

## 현재 제한사항

- OZD 파일은 지원하지 않습니다.
- 자동 팩스 발송은 지원하지 않습니다.
- 카카오톡 자동 발송은 지원하지 않습니다.
- 서버 업로드, DB 저장, 처리 이력 저장은 없습니다.
- 기본 템플릿 좌표는 `src/templates/default.json`에 하드코딩되어 있으며 실제 양식에 맞춰 조정이 필요합니다.

## 로컬 실행

```powershell
npm install
npm run dev
```

기본 개발 서버:

```text
http://127.0.0.1:5891/faxsender/
```

## 빌드

```powershell
npm run build
```

빌드 결과는 `dist/`에 생성됩니다.

## GitHub Pages 배포

`vite.config.ts`의 base는 저장소명 기준으로 설정되어 있습니다.

```ts
base: "/faxsender/"
```

예상 배포 URL:

```text
https://songmihyun.github.io/faxsender/
```

### GitHub Actions 배포

1. GitHub 저장소 이름을 `faxsender`로 생성합니다.
2. 이 프로젝트를 저장소에 push합니다.
3. GitHub 저장소의 `Settings > Pages`로 이동합니다.
4. `Build and deployment`의 `Source`를 `GitHub Actions`로 선택합니다.
5. `main` 브랜치에 push하거나 Actions 탭에서 `Deploy FaxSender Pages` workflow를 수동 실행합니다.
6. workflow가 `npm ci`, `npm run build`, Pages artifact 업로드, Pages 배포를 순서대로 실행합니다.

독립 저장소로 배포할 때는 `.github/workflows/pages.yml`가 `dist`를 GitHub Pages artifact로 배포합니다. 이 프로젝트를 다른 저장소의 하위 폴더로 넣어 관리할 경우에는 workflow의 working directory와 artifact path를 그 구조에 맞게 조정해야 합니다.

### 수동 빌드 배포

GitHub Actions를 쓰지 않고 직접 빌드 결과를 배포하려면 다음 명령을 실행합니다.

```powershell
npm install
npm run build
```

이후 생성된 `dist/` 폴더를 GitHub Pages가 읽는 브랜치 또는 호스팅 경로에 업로드합니다.

## 배포 전 체크리스트

- `vite.config.ts`의 `base`가 `/faxsender/`인지 확인
- `npm run build`가 로컬에서 성공하는지 확인
- `dist/index.html`과 `dist/assets/`가 생성되는지 확인
- GitHub 저장소 `Settings > Pages`의 Source가 `GitHub Actions`인지 확인
- 저장소명이 `faxsender`인지 확인
- 배포 후 `https://songmihyun.github.io/faxsender/`에서 새로고침해도 화면이 유지되는지 확인
- 샘플 PDF 업로드, 처리, 결과 미리보기, 다운로드를 브라우저에서 확인
- PDF가 서버로 전송되지 않는 브라우저 전용 처리 정책을 README에 유지

## 후속 과제

- 실제 동의서 양식별 템플릿 좌표 추가
- 템플릿 좌표 편집 UI
- 체크 PNG asset pool
- 자모 조합 기반 손글씨 서명 엔진
- 여러 페이지/여러 사람 일괄 처리
- 다운로드 전 PDF 품질 옵션

## GitHub Pages 배포 요약

이 저장소는 GitHub Pages 배포를 위해 `vite.config.ts`의 `base`를 `/faxsender/`로 유지합니다.

배포 URL:

```text
https://songmihyun.github.io/faxsender/
```

로컬 실행:

```powershell
npm install
npm run dev
```

빌드:

```powershell
npm run build
```

GitHub Pages 배포:

1. GitHub 저장소 `SongMihyun/faxsender`의 `Settings > Pages`로 이동합니다.
2. `Build and deployment > Source`를 `GitHub Actions`로 설정합니다.
3. `main` 브랜치에 push하면 `.github/workflows/deploy.yml` workflow가 실행됩니다.
4. workflow는 `npm ci`, `npm run build`, `dist` artifact 업로드, Pages 배포 순서로 진행됩니다.

배포 전 체크리스트:

- `vite.config.ts`의 `base`가 `/faxsender/`인지 확인
- `package.json`에 `build` script가 있는지 확인
- `npm run build`가 성공하는지 확인
- GitHub Pages Source가 `GitHub Actions`인지 확인
- 배포 후 `https://songmihyun.github.io/faxsender/` 접속 확인
- 샘플 PDF 업로드, 합성 미리보기, 다운로드 확인
