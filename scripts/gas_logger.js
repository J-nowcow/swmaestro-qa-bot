/**
 * SW마에스트로 Q&A 챗봇 로그 수집기 (Google Apps Script)
 *
 * 설정 방법:
 * 1. Google Sheets에서 새 스프레드시트 생성
 * 2. 첫 행에 헤더 입력: timestamp | question | answer_preview | answer_length
 * 3. 확장 프로그램 → Apps Script 클릭
 * 4. 이 코드를 붙여넣기
 * 5. 배포 → 새 배포 → 유형: 웹 앱
 *    - 실행 주체: 나
 *    - 액세스 권한: 모든 사용자
 * 6. 배포 → URL 복사
 * 7. Streamlit Cloud Secrets에 추가:
 *    LOG_WEBHOOK_URL = "복사한_URL"
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);

    sheet.appendRow([
      data.timestamp || new Date().toISOString(),
      data.question || "",
      data.answer_preview || "",
      data.answer_length || 0,
    ]);

    return ContentService.createTextOutput(
      JSON.stringify({ status: "ok" })
    ).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ status: "error", message: err.toString() })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}
