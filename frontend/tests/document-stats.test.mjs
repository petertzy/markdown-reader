import { render, screen, waitFor } from "@testing-library/react";
import DocumentStats from "../src/components/DocumentStats";

// Mock global fetch
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      words: 100,
      chars_with_spaces: 500,
      chars_without_spaces: 450,
      heading_count: 3,
      reading_time: "1 min read",
    }),
  })
);

test("displays document statistics", async () => {
  render(<DocumentStats content="# Hello\n\nWorld." />);
  await waitFor(() => {
    expect(screen.getByText(/words/)).toBeInTheDocument();
    expect(screen.getByText(/headings/)).toBeInTheDocument();
  });
});