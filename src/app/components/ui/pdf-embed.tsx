interface PdfEmbedProps {
  url: string | null | undefined;
}

const PdfEmbed: React.FC<PdfEmbedProps> = ({ url }) => {
  if (!url) {
    return <p>No PDF available.</p>; // fallback UI
  }

  return (
    <embed
      src={url}
      type="application/pdf"
      width="100%"
      height="600px"
      style={{ border: '1px solid #ccc' }}
    />
  );
};

export default PdfEmbed;