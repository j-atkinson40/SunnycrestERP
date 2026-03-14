import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { hierarchyService } from "@/services/hierarchy-service";
import type { CompanyHierarchyNode, HierarchyResponse } from "@/types/hierarchy";
import { toast } from "sonner";

function HierarchyNode({
  node,
  depth = 0,
}: {
  node: CompanyHierarchyNode;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);

  const levelColors: Record<string, string> = {
    corporate: "bg-blue-100 text-blue-800",
    regional: "bg-green-100 text-green-800",
    location: "bg-amber-100 text-amber-800",
  };

  return (
    <div style={{ marginLeft: depth * 24 }}>
      <div className="flex items-center gap-2 rounded-md border px-3 py-2 mb-1 bg-card hover:bg-muted/50">
        {node.children.length > 0 ? (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs font-mono w-5 text-center text-muted-foreground"
          >
            {expanded ? "v" : ">"}
          </button>
        ) : (
          <span className="w-5 text-center text-muted-foreground text-xs">-</span>
        )}
        <span className="font-medium text-sm">{node.name}</span>
        <span className="text-xs text-muted-foreground">({node.slug})</span>
        {node.hierarchy_level && (
          <Badge
            variant="secondary"
            className={levelColors[node.hierarchy_level] || ""}
          >
            {node.hierarchy_level}
          </Badge>
        )}
        {!node.is_active && (
          <Badge variant="destructive">Inactive</Badge>
        )}
        {node.children.length > 0 && (
          <span className="text-xs text-muted-foreground ml-auto">
            {node.children.length} child{node.children.length !== 1 ? "ren" : ""}
          </span>
        )}
      </div>
      {expanded &&
        node.children.map((child) => (
          <HierarchyNode key={child.id} node={child} depth={depth + 1} />
        ))}
    </div>
  );
}

export default function OrgHierarchyPage() {
  const [data, setData] = useState<HierarchyResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadTree = async () => {
    try {
      setLoading(true);
      const result = await hierarchyService.getTree();
      setData(result);
    } catch {
      toast.error("Failed to load hierarchy");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTree();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Organizational Hierarchy</h1>
          <p className="text-muted-foreground">
            View and manage the parent-child company structure
          </p>
        </div>
        <Button variant="outline" onClick={loadTree} disabled={loading}>
          Refresh
        </Button>
      </div>

      {/* Stats */}
      {data && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{data.total_companies}</div>
              <p className="text-xs text-muted-foreground">Total Companies</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{data.tree.length}</div>
              <p className="text-xs text-muted-foreground">Root Companies</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {data.total_companies - data.tree.length}
              </div>
              <p className="text-xs text-muted-foreground">Child Companies</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tree */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">Company Tree</h2>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : data && data.tree.length > 0 ? (
            <div className="space-y-1">
              {data.tree.map((node) => (
                <HierarchyNode key={node.id} node={node} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">
              No company hierarchy configured. Companies without a parent will
              appear as root nodes.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
