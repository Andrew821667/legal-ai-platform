import bcrypt from 'bcryptjs';

/**
 * Generates a bcrypt hash for the given password
 * @param password - Plain text password
 * @returns Hashed password
 */
export async function hashPassword(password: string): Promise<string> {
  const saltRounds = 10;
  return bcrypt.hash(password, saltRounds);
}

/**
 * Compares a plain text password with a hashed password
 * @param password - Plain text password
 * @param hashedPassword - Hashed password to compare against
 * @returns True if passwords match, false otherwise
 */
export async function verifyPassword(
  password: string,
  hashedPassword: string
): Promise<boolean> {
  return bcrypt.compare(password, hashedPassword);
}

/**
 * Pre-generated hash for 'admin123' (for reference)
 * Use this in NEXT_PUBLIC_ADMIN_PASSWORD env variable
 */
export const ADMIN_PASSWORD_HASH = '$2a$10$8X3jJZK5lNvYq4KzN3FqX.rHqXQ1Y8xGqVxZ6kF1JXvHq8WqKzN3e';
