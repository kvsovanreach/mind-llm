import * as React from "react"
import { cn } from "../../lib/utils"

const Select = ({ children, value, onValueChange }) => {
  const [isOpen, setIsOpen] = React.useState(false)

  return (
    <div className="relative">
      {React.Children.map(children, child => {
        if (child.type === SelectTrigger) {
          return React.cloneElement(child, { isOpen, setIsOpen, value })
        }
        if (child.type === SelectContent) {
          return isOpen ? React.cloneElement(child, { setIsOpen, onValueChange, value }) : null
        }
        return child
      })}
    </div>
  )
}

const SelectTrigger = React.forwardRef(({ className, children, isOpen, setIsOpen, value, ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      className
    )}
    onClick={() => setIsOpen(!isOpen)}
    {...props}
  >
    {React.Children.map(children, child => {
      if (child.type === SelectValue) {
        return React.cloneElement(child, { value })
      }
      return child
    })}
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 opacity-50"><polyline points="6 9 12 15 18 9"></polyline></svg>
  </button>
))
SelectTrigger.displayName = "SelectTrigger"

const SelectValue = ({ placeholder, value }) => (
  <span>{value || placeholder}</span>
)

const SelectContent = React.forwardRef(({ className, children, setIsOpen, onValueChange, value, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "absolute z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-80 top-full mt-1",
      className
    )}
    {...props}
  >
    <div className="p-1">
      {React.Children.map(children, child => {
        if (child.type === SelectItem) {
          return React.cloneElement(child, { setIsOpen, onValueChange, isSelected: child.props.value === value })
        }
        return child
      })}
    </div>
  </div>
))
SelectContent.displayName = "SelectContent"

const SelectItem = React.forwardRef(({ className, children, value, setIsOpen, onValueChange, isSelected, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 hover:bg-accent hover:text-accent-foreground",
      isSelected && "bg-accent",
      className
    )}
    onClick={() => {
      onValueChange(value)
      setIsOpen(false)
    }}
    {...props}
  >
    {isSelected && (
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><polyline points="20 6 9 17 4 12"></polyline></svg>
      </span>
    )}
    {children}
  </div>
))
SelectItem.displayName = "SelectItem"

export {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
}