import { type ParentProps } from "solid-js";
import Layout from "~/components/Layout";

export default function AppLayout(props: ParentProps) {
  return <Layout>{props.children}</Layout>;
}
