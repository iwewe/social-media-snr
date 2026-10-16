export function ErrorMessage({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p role="alert" className="error">
      {error}
    </p>
  );
}
