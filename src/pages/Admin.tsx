import { useState } from "react";
import { trpc } from "@/providers/trpc";
import Layout from "@/components/Layout";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Plus,
  Pencil,
  Trash2,
  LayoutDashboard,
  ExternalLink,
  Search,
  Loader2,
} from "lucide-react";
import { useNavigate } from "react-router";
import { useEffect } from "react";

type DealForm = {
  platformId: string;
  categoryId: string;
  title: string;
  description: string;
  productUrl: string;
  imageUrl: string;
  originalPrice: string;
  salePrice: string;
  discountPercent: string;
  currency: string;
  isFeatured: boolean;
  endDate: string;
};

const emptyForm: DealForm = {
  platformId: "",
  categoryId: "",
  title: "",
  description: "",
  productUrl: "",
  imageUrl: "",
  originalPrice: "",
  salePrice: "",
  discountPercent: "",
  currency: "EGP",
  isFeatured: false,
  endDate: "",
};

export default function Admin() {
  const { user, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (!authLoading && (!user || !isAdmin)) {
      navigate("/");
    }
  }, [authLoading, user, isAdmin, navigate]);

  if (authLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-8 w-8 animate-spin text-orange-600" />
        </div>
      </Layout>
    );
  }

  if (!isAdmin) return null;

  return (
    <Layout>
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-900/30">
              <LayoutDashboard className="h-5 w-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">Manage deals across all platforms</p>
            </div>
          </div>
          <AddDealDialog />
        </div>

        <DealsTable />
      </div>
    </Layout>
  );
}

function DealsTable() {
  const { data: deals, isLoading } = trpc.admin.deals.useQuery();
  const [search, setSearch] = useState("");
  const utils = trpc.useUtils();

  const deleteMutation = trpc.admin.dealDelete.useMutation({
    onSuccess: () => {
      utils.admin.deals.invalidate();
      utils.deals.list.invalidate();
      utils.deals.stats.invalidate();
    },
  });

  const filtered = deals?.filter((d) =>
    d.title.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-orange-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search deals..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="rounded-lg border bg-white dark:bg-gray-900 dark:border-gray-800 overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Discount</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                    No deals found
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((deal) => (
                  <TableRow key={deal.id}>
                    <TableCell className="font-mono text-xs">{deal.id}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        {deal.imageUrl && (
                          <img
                            src={deal.imageUrl}
                            alt=""
                            className="h-10 w-10 rounded object-cover"
                          />
                        )}
                        <div className="max-w-[200px]">
                          <p className="text-sm font-medium truncate">{deal.title}</p>
                          <p className="text-xs text-gray-500">{deal.categoryName}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{deal.platformName}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{deal.categoryName}</TableCell>
                    <TableCell>
                      <Badge className="bg-red-600 text-white">-{deal.discountPercent}%</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <span className="font-semibold">{deal.salePrice}</span>{" "}
                        <span className="text-xs text-gray-400 line-through">{deal.originalPrice}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {deal.isActive && <Badge variant="secondary" className="text-xs">Active</Badge>}
                        {deal.isFeatured && (
                          <Badge className="bg-amber-400 text-amber-900 text-xs">Featured</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => window.open(deal.productUrl, "_blank")}
                        >
                          <ExternalLink className="h-4 w-4 text-gray-500" />
                        </Button>
                        <EditDealDialog deal={deal} />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:text-red-700"
                          onClick={() => {
                            if (confirm("Delete this deal?")) {
                              deleteMutation.mutate({ id: deal.id });
                            }
                          }}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}

function AddDealDialog() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<DealForm>(emptyForm);
  const { data: platforms } = trpc.platforms.list.useQuery();
  const { data: categories } = trpc.categories.list.useQuery();
  const utils = trpc.useUtils();

  const createMutation = trpc.admin.dealCreate.useMutation({
    onSuccess: () => {
      utils.admin.deals.invalidate();
      utils.deals.list.invalidate();
      utils.deals.stats.invalidate();
      setForm(emptyForm);
      setOpen(false);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.platformId || !form.categoryId || !form.title || !form.productUrl || !form.originalPrice || !form.salePrice || !form.discountPercent) return;

    createMutation.mutate({
      platformId: parseInt(form.platformId),
      categoryId: parseInt(form.categoryId),
      title: form.title,
      description: form.description || undefined,
      productUrl: form.productUrl,
      imageUrl: form.imageUrl || undefined,
      originalPrice: form.originalPrice,
      salePrice: form.salePrice,
      discountPercent: parseInt(form.discountPercent),
      currency: form.currency || undefined,
      isFeatured: form.isFeatured || undefined,
      endDate: form.endDate || undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white">
          <Plus className="h-4 w-4 mr-1" />
          Add Deal
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add New Deal</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DealFormFields form={form} setForm={setForm} platforms={platforms ?? []} categories={categories ?? []} />
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button type="button" variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white"
            >
              {createMutation.isPending ? "Creating..." : "Create Deal"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditDealDialog({ deal }: { deal: any }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<DealForm>({
    platformId: String(deal.platformId),
    categoryId: String(deal.categoryId),
    title: deal.title,
    description: deal.description ?? "",
    productUrl: deal.productUrl,
    imageUrl: deal.imageUrl ?? "",
    originalPrice: deal.originalPrice,
    salePrice: deal.salePrice,
    discountPercent: String(deal.discountPercent),
    currency: deal.currency,
    isFeatured: deal.isFeatured,
    endDate: deal.endDate ? new Date(deal.endDate).toISOString().slice(0, 16) : "",
  });

  const { data: platforms } = trpc.platforms.list.useQuery();
  const { data: categories } = trpc.categories.list.useQuery();
  const utils = trpc.useUtils();

  const updateMutation = trpc.admin.dealUpdate.useMutation({
    onSuccess: () => {
      utils.admin.deals.invalidate();
      utils.deals.list.invalidate();
      utils.deals.stats.invalidate();
      setOpen(false);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate({
      id: deal.id,
      data: {
        platformId: parseInt(form.platformId),
        categoryId: parseInt(form.categoryId),
        title: form.title,
        description: form.description || undefined,
        productUrl: form.productUrl,
        imageUrl: form.imageUrl || undefined,
        originalPrice: form.originalPrice,
        salePrice: form.salePrice,
        discountPercent: parseInt(form.discountPercent),
        currency: form.currency,
        isFeatured: form.isFeatured,
        isActive: true,
        endDate: form.endDate || undefined,
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Pencil className="h-4 w-4 text-gray-500" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Deal</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DealFormFields form={form} setForm={setForm} platforms={platforms ?? []} categories={categories ?? []} />
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button type="button" variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              type="submit"
              disabled={updateMutation.isPending}
              className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white"
            >
              {updateMutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DealFormFields({
  form,
  setForm,
  platforms,
  categories,
}: {
  form: DealForm;
  setForm: React.Dispatch<React.SetStateAction<DealForm>>;
  platforms: Array<{ id: number; name: string }>;
  categories: Array<{ id: number; name: string }>;
}) {
  const update = (field: keyof DealForm, value: any) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Platform *</Label>
          <Select value={form.platformId} onValueChange={(v) => update("platformId", v)}>
            <SelectTrigger>
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              {platforms.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Category *</Label>
          <Select value={form.categoryId} onValueChange={(v) => update("categoryId", v)}>
            <SelectTrigger>
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>Title *</Label>
        <Input value={form.title} onChange={(e) => update("title", e.target.value)} placeholder="Product title" />
      </div>

      <div className="space-y-1.5">
        <Label>Description</Label>
        <Textarea
          value={form.description}
          onChange={(e) => update("description", e.target.value)}
          placeholder="Brief product description"
          rows={2}
        />
      </div>

      <div className="space-y-1.5">
        <Label>Product URL *</Label>
        <Input value={form.productUrl} onChange={(e) => update("productUrl", e.target.value)} placeholder="https://..." />
      </div>

      <div className="space-y-1.5">
        <Label>Image URL</Label>
        <Input value={form.imageUrl} onChange={(e) => update("imageUrl", e.target.value)} placeholder="https://..." />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label>Original Price *</Label>
          <Input value={form.originalPrice} onChange={(e) => update("originalPrice", e.target.value)} placeholder="9999" />
        </div>
        <div className="space-y-1.5">
          <Label>Sale Price *</Label>
          <Input value={form.salePrice} onChange={(e) => update("salePrice", e.target.value)} placeholder="4999" />
        </div>
        <div className="space-y-1.5">
          <Label>Discount % *</Label>
          <Input value={form.discountPercent} onChange={(e) => update("discountPercent", e.target.value)} placeholder="50" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Currency</Label>
          <Input value={form.currency} onChange={(e) => update("currency", e.target.value)} placeholder="EGP" />
        </div>
        <div className="space-y-1.5">
          <Label>End Date</Label>
          <Input
            type="datetime-local"
            value={form.endDate}
            onChange={(e) => update("endDate", e.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Checkbox
          id="featured"
          checked={form.isFeatured}
          onCheckedChange={(v) => update("isFeatured", !!v)}
        />
        <Label htmlFor="featured" className="text-sm cursor-pointer">
          Feature this deal on homepage
        </Label>
      </div>
    </>
  );
}
