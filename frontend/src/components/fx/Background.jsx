/** Fixed ambient backdrop: drifting aurora blobs, a perspective grid and a faint noise layer. */
export default function Background() {
  return (
    <div className="bg-fx" aria-hidden="true">
      <div className="aurora a1" />
      <div className="aurora a2" />
      <div className="aurora a3" />
      <div className="bg-grid" />
      <div className="bg-noise" />
    </div>
  );
}
