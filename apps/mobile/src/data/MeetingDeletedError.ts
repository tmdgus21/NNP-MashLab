export class MeetingDeletedError extends Error {
  constructor() { super('방장이 삭제한 모임입니다. 모임 목록에서 다른 모임을 선택해 주세요.'); }
}
