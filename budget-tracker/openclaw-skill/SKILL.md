---
name: budget-tracker
description: 문자/영수증 사진을 파싱해서 가계부 API에 자동 기록
requires:
  bins: [curl]
---

# 가계부 자동 기록

사용자가 카드 결제 문자나 영수증 사진을 보내면, 아래 절차로 가계부 API(`http://localhost:8000`)에 기록한다.

## 절차

1. 메시지 내용(텍스트 또는 사진 속 정보)에서 다음 정보를 추출한다:
   - `date`: 결제 날짜 (ISO 형식, 예: `2026-08-03T00:00:00`). 명시 안 되어 있으면 오늘 날짜 사용.
   - `title`: 가맹점/항목명
   - `amount`: 금액 (정수, 원 단위)
   - `type`: `expense` 또는 `income`
   - `memo`: 짧은 요약 (선택)

2. 카테고리/자산 ID를 찾기 위해 먼저 조회한다:
   ```bash
   curl -s http://localhost:8000/categories/
   curl -s http://localhost:8000/assets/
   ```
   반환된 목록에서 이름이 가장 잘 맞는 항목의 `id`를 `category_id`, `asset_id`로 사용한다. 마땅한 게 없으면 `null`로 둔다.

3. 아래 형식으로 거래를 기록한다:
   ```bash
   curl -s -X POST http://localhost:8000/transactions/ \
     -H "Content-Type: application/json" \
     -d '{
       "date": "<ISO 날짜>",
       "title": "<항목명>",
       "amount": <금액>,
       "type": "<expense 또는 income>",
       "category_id": <카테고리ID 또는 null>,
       "asset_id": <자산ID 또는 null>,
       "source": "<sms_auto 또는 photo_auto>",
       "memo": "<메모>",
       "confirmed": false
     }'
   ```
   - `source`는 문자를 받았으면 `sms_auto`, 사진을 받았으면 `photo_auto`.
   - `confirmed`는 항상 `false`로 보낸다 (나중에 사람이 대시보드에서 검토/확정).

4. 기록 완료 후 사용자에게 무엇을 기록했는지 간단히 답장한다 (예: "스타벅스 5,000원으로 기록했어요").

5. API가 실패(에러 응답)하면 원문 그대로 사용자에게 보여주고 다시 시도할지 묻는다.

## 자산/카테고리 등록

사용자가 "카드 등록해줘", "OO은행 계좌 추가" 같이 새 자산이나 카테고리를 만들어달라고 하면:

```bash
curl -s -X POST http://localhost:8000/assets/ \
  -H "Content-Type: application/json" \
  -d '{"name": "<자산명>", "type": "<cash 또는 bank 또는 card>", "balance": <잔액 또는 null>}'

curl -s -X POST http://localhost:8000/categories/ \
  -H "Content-Type: application/json" \
  -d '{"name": "<카테고리명>"}'
```

등록 전에 2번 절차로 목록을 조회해서 이미 같은 이름이 있는지 먼저 확인하고, 있으면 중복 생성하지 말고 그 사실을 알린다. 등록 완료 후 생성된 `id`와 함께 결과를 알려준다.

## 자산 삭제

사용자가 "OO카드 삭제해줘", "OO계좌 지워줘" 같이 자산 삭제를 요청하면:

1. 2번 절차(`GET /assets/`)로 목록을 조회해서 이름이 일치하는 자산의 `id`를 찾는다. 일치하는 게 없으면 그렇게 알린다.
2. 삭제는 되돌릴 수 없으므로, 실행 전에 반드시 "OO(자산명)을 삭제할까요?"라고 되물어 사용자 확인을 받는다.
3. 확인되면 삭제한다:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/assets/<자산ID>
   ```
   - `204`면 성공, `404`면 해당 자산이 없다는 뜻.
4. 결과를 사용자에게 알려준다.
