import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { potatoColors } from '../theme/colors';

export function BrandLogo() {
  return (
    <View style={styles.container}>
      <Image
        accessibilityLabel="Potato Meet 로고"
        resizeMode="contain"
        source={require('../../assets/images/potato_logo.png')}
        style={styles.logo}
      />
      <Text style={styles.wordmark}>
        <Text style={styles.potato}>potato </Text>
        <Text style={styles.meet}>meet</Text>
      </Text>
      <Text style={styles.tagline}>함께하는 일정, 더 쉬운 약속</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  logo: {
    width: 130,
    height: 130,
    marginBottom: 10,
  },
  wordmark: {
    fontSize: 32,
    fontWeight: '800',
  },
  potato: {
    color: potatoColors.brown,
  },
  meet: {
    color: potatoColors.orange,
  },
  tagline: {
    marginTop: 6,
    color: '#666666',
    fontSize: 15,
  },
});
