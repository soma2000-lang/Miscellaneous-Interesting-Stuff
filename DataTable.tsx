'use client';

import React, { useEffect, useState } from 'react';
import { toast } from "react-toastify";
import { useReactTable, flexRender, getCoreRowModel, getSortedRowModel, SortingState } from "@tanstack/react-table";
import { FaSort, FaSortUp, FaSortDown, FaEdit, FaTrash } from "react-icons/fa";
import { getUsers } from "../services/api";

type User = {
    code: string;
    name: string;
    city: string;
    country: string;
};

const SortIcon = ({ isSorted }: { isSorted: 'asc' | 'desc' | false }) => {
    if (!isSorted) return <FaSort className="inline ml-1" />;
    return isSorted === "asc" ? <FaSortUp className="inline ml-1" /> : <FaSortDown className="inline ml-1" />;
};

const DataTable = ({ onEdit, refresh }: { onEdit: (user: User) => void, refresh: boolean }) => {
    const [data, setData] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [sorting, setSorting] = useState<SortingState>([]);

    useEffect(() => {
        fetchUsers();
    }, [refresh]);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const response = await getUsers();

            if (!response || !response[0]) {
                throw new Error('Invalid response data');
            }

            const transformedData = Object.entries(response[0]).map(([, value]) => {
                const user = value as User;

                if (!user || !user.code) {
                    return null;
                }

                return {
                    code: user.code,
                    name: user.name,
                    city: user.city,
                    country: user.country,
                    updatedAt: new Date().toISOString(),
                };
            }).filter(Boolean) as User[];
            setData(transformedData);
        } catch {
            toast.error("Failed to fetch users");
        }
        finally {
            setLoading(false);
        }
    }

    const columns = [
        { accessorKey: "code", header: "ID" },
        { accessorKey: "name", header: "Name" },
        { accessorKey: "city", header: "City" },
        { accessorKey: "country", header: "Country" },
        { accessorKey: "updatedAt", header: "Updated At" },
        {
            id: "actions",
            header: "Actions",
            cell: ({ row }: { row: { original: User } }) => (
                <div className="flex gap-2">
                    <button className="text-blue-500" onClick={() => onEdit(row.original)}>
                        <FaEdit />
                    </button>
                    <button className="text-red-500">
                        <FaTrash />
                    </button>
                </div>
            ),
        },
    ];

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        onSortingChange: setSorting,
        state: {
            sorting,
        },
    })

    if (loading) return <p>Loading...</p>;

    return (
        <table className='w-full border-collapse border border-gray-200'>
            <thead>
                {
                    table.getHeaderGroups().map((headerGroup) => (
                        <tr key={headerGroup.id} className="border">
                            {headerGroup.headers.map((header) => (
                                <th
                                    key={header.id}
                                    onClick={header.column.getToggleSortingHandler()}
                                    className="border p-2 cursor-pointer"
                                >
                                    {flexRender(header.column.columnDef.header, header.getContext())}
                                    <SortIcon isSorted={header.column.getIsSorted()} />
                                </th>
                            ))}
                        </tr>
                    ))
                }
            </thead>
            <tbody>
                {
                    table.getRowModel().rows.map((row) => (
                        <tr key={row.id} className="border">
                            {row.getVisibleCells().map((cell) => (
                                <td key={cell.id} className="border p-2">
                                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                </td>
                            ))}
                        </tr>
                    ))
                }
            </tbody>
        </table>
    )
}

export default DataTable