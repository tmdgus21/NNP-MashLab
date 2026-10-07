import AsyncStorage from '@react-native-async-storage/async-storage';
import { MockRepository } from './MockRepository';
import { Repository } from './RepositoryPort';

export const mockRepository = new MockRepository(AsyncStorage);
// Replace this one injection point with new HttpRepository(url, secureTokenProvider).
export const repository: Repository = mockRepository;
