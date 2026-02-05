-- Add 2x_week and 3x_week frequency options for habits
-- Migration: 008_add_2x_3x_week_frequencies.sql

ALTER TABLE todos.habits DROP CONSTRAINT habits_frequency_check;

ALTER TABLE todos.habits ADD CONSTRAINT habits_frequency_check
    CHECK (frequency IN ('daily', 'weekly', '2x_week', '3x_week', 'monthly', 'custom'));
