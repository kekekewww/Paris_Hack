export class ServiceError extends Error {
  constructor(code, message, status = 0) {
    super(message);
    this.name = 'ServiceError';
    this.code = code;
    this.status = status;
  }
}
