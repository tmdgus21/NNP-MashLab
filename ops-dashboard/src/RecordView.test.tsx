// @vitest-environment jsdom
import {afterEach,describe,it,expect} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {RecordView,clock} from './RecordView';
afterEach(cleanup);
describe('Read-only operational records',()=>{
 it('formats midnight without wrapping the input range',()=>{expect(clock(1440)).toBe('24:00');expect(clock(570)).toBe('09:30')});
 it('distinguishes feasible from optimal and missing confirmation',()=>{render(<RecordView value={{solverStatus:'FEASIBLE',finalizedAt:null}}/>);expect(screen.getByText('배정 가능 · 최적성 미확인')).toBeTruthy();expect(screen.getByText('미기록')).toBeTruthy()});
 it('resolves participant names and preserves unavailable intervals',()=>{render(<RecordView people={{p:'참여자'}} value={{memberId:'p',unavailable:[{date:'2026-11-01',start:540,end:600}]}}/>);expect(screen.getAllByText('참여자').length).toBeGreaterThan(0);expect(screen.getByText('불가 시간')).toBeTruthy();expect(screen.getByText('09:00')).toBeTruthy()});
 it('does not invent data for empty records',()=>{render(<RecordView value={[]}/>);expect(screen.getByText('기록 없음')).toBeTruthy()});
});
