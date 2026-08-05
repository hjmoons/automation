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
   - `type`: `expense`, `income`, 또는 계좌 간 이체면 `transfer` (이체면 `asset_id`는 보내는 계좌, `to_asset_id`는 받는 계좌)
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
       "type": "<expense, income, transfer 중 하나>",
       "category_id": <카테고리ID 또는 null>,
       "asset_id": <자산ID 또는 null>,
       "to_asset_id": <이체 받는 자산ID, 이체 아니면 null>,
       "source": "<sms_auto 또는 photo_auto>",
       "memo": "<메모>"
     }'
   ```
   - `source`는 문자를 받았으면 `sms_auto`, 사진을 받았으면 `photo_auto`.
   - 응답으로 받은 `id`를 기억해둔다 (바로 이어서 정정 요청이 오면 이 거래를 가리키는 것).

4. 기록 완료 후 사용자에게 무엇을 기록했는지 간단히 답장한다 (예: "스타벅스 5,000원으로 기록했어요").

5. API가 실패(에러 응답)하면 원문 그대로 사용자에게 보여주고 다시 시도할지 묻는다.

## 거래 수정

사용자가 방금 기록된 내용을 정정하거나("아니 4,500원이야", "카테고리 잘못됐어") 예전 거래를 고쳐달라고 하면:

1. 어떤 거래인지 특정한다:
   - 방금 이 대화에서 기록한 거래면 3번 절차에서 기억해둔 `id`를 그대로 쓴다.
   - 그게 아니면 `GET /transactions/`로 조회해서 날짜/금액/항목명으로 후보를 좁힌다.
   - 후보가 여러 개면 사용자에게 어떤 건지 되묻는다. 하나로 특정되면 바로 진행한다 (되묻지 않음).
2. 특정되면 수정한다:
   ```bash
   curl -s -X PATCH http://localhost:8000/transactions/<거래ID> \
     -H "Content-Type: application/json" \
     -d '{"amount": <새 금액>, "title": "<새 항목명>", "category_id": <새 카테고리ID>}'
   ```
   바뀌는 필드만 body에 넣는다 (예: 금액만 고치면 `amount`만).
3. 수정 결과를 사용자에게 알려준다.

## 자산/카테고리 등록

사용자가 "카드 등록해줘", "OO은행 계좌 추가", "식비 카테고리 만들어줘" 같이 새 자산이나 카테고리를 만들어달라고 하면:

```bash
curl -s -X POST http://localhost:8000/assets/ \
  -H "Content-Type: application/json" \
  -d '{"name": "<자산명>", "type": "<cash 또는 bank 또는 card>", "balance": <잔액 또는 null>}'

curl -s -X POST http://localhost:8000/categories/ \
  -H "Content-Type: application/json" \
  -d '{"name": "<카테고리명>", "type": "<income 또는 expense>"}'
```

- 카테고리는 수입용인지 지출용인지(`type`) 반드시 물어보거나 문맥으로 판단해서 넣는다 (애매하면 사용자에게 확인).
- 등록 전에 2번 절차로 목록을 조회해서 이미 같은 이름이 있는지 먼저 확인하고, 있으면 중복 생성하지 말고 그 사실을 알린다. 등록 완료 후 생성된 `id`와 함께 결과를 알려준다.

## 자산/카테고리 수정

사용자가 "OO카드 이름 바꿔줘", "식비 카테고리를 지출로 바꿔줘" 같이 요청하면, 이름으로 대상을 찾은 뒤 바뀌는 필드만 보내서 수정한다:

```bash
curl -s -X PATCH http://localhost:8000/assets/<자산ID> \
  -H "Content-Type: application/json" \
  -d '{"name": "<새 이름>"}'

curl -s -X PATCH http://localhost:8000/categories/<카테고리ID> \
  -H "Content-Type: application/json" \
  -d '{"type": "<income 또는 expense>"}'
```

## 자산/카테고리 삭제

사용자가 "OO카드 삭제해줘", "OO계좌 지워줘", "OO카테고리 삭제해줘" 같이 삭제를 요청하면:

1. 2번 절차(`GET /assets/`, `GET /categories/`)로 목록을 조회해서 이름이 일치하는 항목의 `id`를 찾는다. 일치하는 게 없으면 그렇게 알린다.
2. 삭제는 되돌릴 수 없으므로, 실행 전에 반드시 "OO을 삭제할까요?"라고 되물어 사용자 확인을 받는다.
3. 확인되면 삭제한다:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/assets/<자산ID>
   curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/categories/<카테고리ID>
   ```
   - `204`면 성공, `404`면 해당 항목이 없다는 뜻.
4. 결과를 사용자에게 알려준다.
