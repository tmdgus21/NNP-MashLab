import React from 'react';
import { Text, View } from 'react-native';
import type Renderer from 'react-test-renderer';

export function textContent(value: React.ReactNode): string {
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(textContent).join('');
  }
  if (React.isValidElement<{ children?: React.ReactNode }>(value)) {
    return textContent(value.props.children);
  }
  return '';
}

export function findButton(
  tree: Renderer.ReactTestRenderer,
  label: string,
): Renderer.ReactTestInstance {
  const candidates = tree.root.findAll(
    button =>
      typeof button.props.onPress === 'function' &&
      button
        .findAllByType(Text)
        .some(text => textContent(text.props.children) === label),
  );
  const semanticButtons = candidates.filter(
    button => button.props.accessibilityRole === 'button',
  );
  const buttons = semanticButtons.length > 0 ? semanticButtons : candidates;
  if (buttons.length === 0) {
    throw new Error(`Could not find a button named "${label}".`);
  }
  return buttons[0];
}

export function hasText(
  tree: Renderer.ReactTestRenderer,
  expected: string,
): boolean {
  return tree.root
    .findAllByType(Text)
    .some(element => textContent(element.props.children) === expected);
}

export function findViewsWithProps(
  tree: Renderer.ReactTestRenderer,
  props: Record<string, unknown>,
): Renderer.ReactTestInstance[] {
  return tree.root
    .findAllByType(View)
    .filter(view =>
      Object.entries(props).every(
        ([key, value]) => view.props[key] === value,
      ),
    );
}
