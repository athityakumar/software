{-
  Quick and dirty client lib generation. Structured for dynamically typed or type-inferred languages (does not keep type information).
  Bootstraps lib generation into Haskell compilation (evil TH usage, but very convenient).
-}

module Templating where

import Auxiliary

import Data.List
import Data.Char
import qualified Data.Aeson.TH as A
import Language.Haskell.TH
import System.IO.Unsafe

{- quasi-AST -> Code -}

data TDecl = TFuncDef String [String] TExpr

data TExpr = TMapE [(String, TExpr)] | TListE [TExpr] | TVarE String

data TLang = Python deriving (Show)

languages = [Python]

ext Python = ".py"

expGen :: TLang -> TExpr -> String
expGen Python (TVarE s) = s
expGen Python (TListE e) = "[" ++ concat (intersperse ", " $ map (expGen Python) e) ++ "]"
expGen Python (TMapE e) = "{" ++ concat (intersperse ", " $ map (\(k, e) -> "'" ++ k ++ "': " ++ expGen Python e) e) ++ "}"

declGen :: TLang -> TDecl -> String
declGen Python (TFuncDef n a e) = n ++ " = lambda " ++ concat (intersperse ", " a) ++ ": " ++ expGen Python e

{- Haskell Data Defs (Aeson-serialized) -> quasi-AST -}

base = "## < ASLAM AUTOGENERATED CODE; DO NOT MODIFY > ##\n\n"

tvn = map return $ ['a' .. 'z']

nameMod = map toLower . dropPrefix . show

consMod = A.constructorTagModifier defaultJSONOptions . dropPrefix . show

recMod = A.fieldLabelModifier defaultJSONOptions . dropPrefix . show

dropPrefix = tail . dropWhile ((/=) '.')

deriveConstructors x = do
  (TyConI (DataD _ n _ cs _)) <- reify x
  let r = flip map cs $ \x -> case x of
        (NormalC cn as) -> TFuncDef (consMod cn) (take (length as) tvn) (TMapE [(consMod cn, if length as == 1 then TVarE (head tvn) else TListE (map TVarE $ take (length as) tvn))])
        (RecC cn as) -> TFuncDef (consMod cn) (take (length as) tvn) (TMapE [(consMod cn, TMapE (map (\((k, _, _), v) -> (recMod k, TVarE v)) $ zip as tvn))])
      z = unsafePerformIO $ do
            sequence $ map (\lang -> writeFile ("libs/" ++ map toLower (show lang) ++ "/aslam/" ++ nameMod n ++ ext lang) ((++) base $ concat $ intersperse "\n\n" $ map (declGen lang) r)) languages
      in z `seq` return []
