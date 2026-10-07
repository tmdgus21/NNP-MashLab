import React from 'react';
import { Text } from 'react-native';
import Renderer, { act } from 'react-test-renderer';
import { PlanTable } from '../src/ui/PlanTable';
import { fixture } from '../src/data/fixtures';
test('assignment table keeps role/time/person/status format for confirmed rows', async () => {
  const m = fixture('finalized');
  let tree: Renderer.ReactTestRenderer;
  await act(async () => {
    tree = Renderer.create(<PlanTable plan={m.plan} meeting={m} />);
  });
  const texts = tree!.root
    .findAllByType(Text)
    .map(t => t.props.children)
    .flat()
    .join(' ');
  ['역할', '시간', '담당자', '상태', '확정', '진행', '촬영'].forEach(v =>
    expect(texts).toContain(v),
  );
  await act(async () => tree!.unmount());
});
