/**
 * Type declarations for custom Jest matchers
 */

declare global {
  namespace jest {
    interface Matchers<R> {
      toBeWithinRange(floor: number, ceiling: number): R;
      toBeValidAvatarApiResponse(): R;
    }
  }
}

export {};