import { describe, it, expect } from 'vitest';
import { z } from 'zod';

export const searchFilterSchema = z
  .object({
    start_date: z.string().optional(),
    end_date: z.string().optional(),
    start_time: z.string().optional(),
    end_time: z.string().optional(),
    city: z.string().optional(),
    district: z.string().optional(),
  })
  .refine(
    (data) => {
      if (data.start_date && data.end_date) {
        return new Date(data.end_date) >= new Date(data.start_date);
      }
      return true;
    },
    {
      message: 'End date must be greater than or equal to start date',
      path: ['end_date'],
    }
  );

describe('Incident Search Form Zod Validation', () => {
  it('passes when valid start_date and later end_date are provided', () => {
    const validData = {
      start_date: '2021-01-07',
      end_date: '2021-01-10',
      start_time: '09:00',
      end_time: '18:00',
      city: 'Cairo',
      district: 'District 1',
    };

    const result = searchFilterSchema.safeParse(validData);
    expect(result.success).toBe(true);
  });

  it('passes when dates are identical (single day search)', () => {
    const singleDayData = {
      start_date: '2021-01-07',
      end_date: '2021-01-07',
    };

    const result = searchFilterSchema.safeParse(singleDayData);
    expect(result.success).toBe(true);
  });

  it('fails with validation error when end_date is earlier than start_date', () => {
    const invalidData = {
      start_date: '2021-01-10',
      end_date: '2021-01-05',
    };

    const result = searchFilterSchema.safeParse(invalidData);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].message).toBe(
        'End date must be greater than or equal to start date'
      );
      expect(result.error.issues[0].path).toEqual(['end_date']);
    }
  });

  it('passes with empty/optional filter fields', () => {
    const emptyData = {
      start_date: '',
      end_date: '',
      city: '',
    };

    const result = searchFilterSchema.safeParse(emptyData);
    expect(result.success).toBe(true);
  });
});
