import React from 'react';
import Svg, { Path, Rect } from 'react-native-svg';

export function NavigationIcon({
  name,
  color,
}: {
  name: string;
  color: string;
}) {
  return (
    <Svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={1.8}
      accessible={false}
    >
      {name === '현황' ? (
        <>
          <Rect x={3} y={3} width={18} height={18} rx={5} />
          <Path d="M7 16v-4m5 4V7m5 9v-6" strokeLinecap="round" />
        </>
      ) : name === '내 조건' ? (
        <>
          <Rect x={3} y={5} width={18} height={16} rx={4} />
          <Path d="M7 3v4m10-4v4M3 11h18m-14 5h3m4 0h3" strokeLinecap="round" />
        </>
      ) : (
        <>
          <Rect x={4} y={3} width={16} height={18} rx={4} />
          <Path
            d="m8 12 3 3 5-6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
    </Svg>
  );
}
