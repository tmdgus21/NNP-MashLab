import { Repository } from './RepositoryPort';
import { HttpRepository } from './HttpRepository';
import { secureSession } from './secureSession';
import { API_BASE_URL } from '../config/runtime.generated';

export const repository: Repository = new HttpRepository(API_BASE_URL, async () => (await secureSession.read())?.token ?? null, fetch, secureSession);
