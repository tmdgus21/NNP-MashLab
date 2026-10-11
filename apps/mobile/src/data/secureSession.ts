import * as Keychain from 'react-native-keychain';
import {z} from 'zod';
import {StoredSession} from './sessionTypes';
import { NativeModules } from 'react-native';

const service = 'com.conditionalok.app.sessions.v1';
const storedSchema = z.object({meetingId:z.string(),actorId:z.string(),token:z.string(),title:z.string(),name:z.string()});
const vaultSchema = z.object({active:z.string().nullable(), sessions:z.record(z.string(),storedSchema), pending:z.record(z.string(),z.string()).default({})});
async function load() {
  const entry = await Keychain.getGenericPassword({service});
  return entry ? vaultSchema.parse(JSON.parse(entry.password)) : {active:null, sessions:{} as Record<string,StoredSession>, pending:{} as Record<string,string>};
}
async function persist(data: z.infer<typeof vaultSchema>) {
  const result = await Keychain.setGenericPassword('conditional-ok', JSON.stringify(data), {service, accessible:Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY});
  if (!result) {throw new Error('참가자 인증을 안전하게 저장하지 못했습니다.');}
}
export const secureSession = {
  async read() {const data=await load(); return data.active ? data.sessions[data.active] ?? null : null;},
  async save(value: StoredSession) {const data=await load(); data.sessions[value.meetingId]=value; data.active=value.meetingId; await persist(data);},
  async list() {return Object.values((await load()).sessions);},
  async activate(id:string) {const data=await load(); if(!data.sessions[id]) {throw new Error('저장된 참가자 인증이 없습니다.');} data.active=id; await persist(data);},
  async requestKey(fingerprint:string) {const data=await load();if(!data.pending[fingerprint]){data.pending[fingerprint]=await NativeModules.ConditionalOKInvitation.newRequestKey();await persist(data);}return data.pending[fingerprint];},
  async completeRequest(fingerprint:string) {const data=await load();delete data.pending[fingerprint];await persist(data);},
};
