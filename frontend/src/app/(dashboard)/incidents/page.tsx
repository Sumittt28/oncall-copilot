"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, IncidentsListResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Plus, AlertCircle, Clock } from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";

const SEVERITY_VARIANTS: Record<string, "destructive" | "secondary" | "default" | "outline"> = {
  "SEV-1": "destructive",
  "SEV-2": "destructive",
  "SEV-3": "secondary",
  "SEV-4": "outline",
};

const STATUS_VARIANTS: Record<string, "destructive" | "secondary" | "default" | "outline"> = {
  open: "destructive",
  investigating: "secondary",
  identified: "secondary",
  monitoring: "default",
  resolved: "outline",
};

export default function IncidentsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newIncident, setNewIncident] = useState({
    title: "",
    description: "",
    severity: "SEV-3" as "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4",
  });

  const { data, isLoading, error } = useQuery<IncidentsListResponse>({
    queryKey: ["incidents", statusFilter],
    queryFn: () =>
      api.getIncidents({
        status: statusFilter === "all" ? undefined : statusFilter,
      }),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createIncident(newIncident),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setIsCreateOpen(false);
      setNewIncident({ title: "", description: "", severity: "SEV-3" });
      toast.success("Incident created successfully");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  if (error) {
    return (
      <div className="p-8">
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">Failed to load incidents</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Incidents</h1>
          <p className="text-muted-foreground">
            Manage and track all incidents
          </p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Incident
            </Button>
          </DialogTrigger>
          <DialogContent>
            <form onSubmit={handleCreate}>
              <DialogHeader>
                <DialogTitle>Create Incident</DialogTitle>
                <DialogDescription>
                  Report a new incident to start tracking and investigation.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    placeholder="Brief description of the issue"
                    value={newIncident.title}
                    onChange={(e) =>
                      setNewIncident({ ...newIncident, title: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Detailed description of what's happening..."
                    value={newIncident.description}
                    onChange={(e) =>
                      setNewIncident({ ...newIncident, description: e.target.value })
                    }
                    required
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="severity">Severity</Label>
                  <Select
                    value={newIncident.severity}
                    onValueChange={(value: "SEV-1" | "SEV-2" | "SEV-3" | "SEV-4") =>
                      setNewIncident({ ...newIncident, severity: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select severity" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="SEV-1">SEV-1 (Critical)</SelectItem>
                      <SelectItem value="SEV-2">SEV-2 (Major)</SelectItem>
                      <SelectItem value="SEV-3">SEV-3 (Minor)</SelectItem>
                      <SelectItem value="SEV-4">SEV-4 (Low)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsCreateOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Creating..." : "Create Incident"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-4">
            <div className="space-y-1">
              <Label>Status Filter</Label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="investigating">Investigating</SelectItem>
                  <SelectItem value="identified">Identified</SelectItem>
                  <SelectItem value="monitoring">Monitoring</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="ml-auto text-sm text-muted-foreground">
              {data?.total ?? 0} incident{data?.total !== 1 ? "s" : ""}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Incidents Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">
              Loading incidents...
            </div>
          ) : data?.items.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No incidents found</p>
              <p className="text-sm">Create your first incident to get started</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Incident</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((incident) => (
                  <TableRow key={incident.id}>
                    <TableCell>
                      <Link
                        href={`/incidents/${incident.id}`}
                        className="font-medium hover:underline"
                      >
                        {incident.title}
                      </Link>
                      <p className="text-sm text-muted-foreground line-clamp-1">
                        {incident.description}
                      </p>
                    </TableCell>
                    <TableCell>
                      <Badge variant={SEVERITY_VARIANTS[incident.severity]}>
                        {incident.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANTS[incident.status]}>
                        {incident.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{incident.owner.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDistanceToNow(new Date(incident.created_at), {
                          addSuffix: true,
                        })}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
