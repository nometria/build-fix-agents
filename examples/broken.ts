// Example TypeScript file with common build errors

// Error 1: Unused import
import { useState, useEffect, useCallback } from 'react';
import { SomeUnusedHelper } from './helpers';

// Error 2: Duplicate variable declaration
const API_BASE = 'https://api.example.com';
const API_BASE = 'https://api.example.com/v2';  // duplicate!

// Error 3: Missing export reference
function internalHelper(data: string): string {
  return data.trim();
}

// This function references UserService which is not exported from its module
function processUser(id: string) {
  const user = UserService.findById(id);  // UserService is not exported
  return user;
}

// Normal working code
export function greet(name: string): string {
  const [count, setCount] = useState(0);
  return `Hello, ${name}`;
}
